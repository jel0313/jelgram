"""画像の保存先(Supabase Storage)とのやり取り(9-5・9-7)。

S3 互換のストレージを、HTTP の API で操作する。テストでは同じメソッドを持つ偽物に差し替える(20-3)。
秘密鍵を使うのはサーバーだけ。ブラウザには、期限付きの署名付き URL だけを渡す。
"""

import logging
from typing import Annotated, Protocol
from urllib.parse import quote

import httpx2
from fastapi import Depends, Request

from app.core.exceptions import ServiceUnavailableError

logger = logging.getLogger(__name__)


class StorageError(ServiceUnavailableError):
    code = "storage_unavailable"
    message = "画像の保存先に接続できません。時間をおいてもう一度お試しください"


class StorageClient(Protocol):
    """ストレージの操作(本物も偽物もこの形にそろえる)。"""

    def upload(
        self, path: str, data: bytes, content_type: str, *, upsert: bool = False
    ) -> None: ...

    def download(self, path: str) -> bytes: ...

    def delete(self, paths: list[str]) -> None: ...

    def signed_urls(self, paths: list[str], expires_in: int) -> dict[str, str]: ...

    def signed_upload_url(self, path: str) -> str: ...


class SupabaseStorage:
    """Supabase Storage の REST API を呼ぶクライアント。"""

    def __init__(self, *, supabase_url: str, secret_key: str, bucket: str, timeout: float = 10):
        self.base_url = f"{supabase_url.rstrip('/')}/storage/v1"
        self.bucket = bucket
        self.http = httpx2.Client(
            base_url=self.base_url,
            headers={"apikey": secret_key},
            timeout=timeout,
        )

    def close(self) -> None:
        self.http.close()

    def _object_path(self, path: str) -> str:
        return f"/object/{self.bucket}/{quote(path)}"

    def _request(self, method: str, url: str, **kwargs) -> httpx2.Response:  # type: ignore[no-untyped-def]
        try:
            response = self.http.request(method, url, **kwargs)
            response.raise_for_status()
        except httpx2.HTTPError as e:
            # 秘密鍵がログに出ないよう、URL とステータスだけを残す
            status = getattr(getattr(e, "response", None), "status_code", None)
            logger.warning("ストレージの呼び出しに失敗", extra={"url": url, "status": status})
            raise StorageError from e
        return response

    def upload(self, path: str, data: bytes, content_type: str, *, upsert: bool = False) -> None:
        self._request(
            "POST",
            self._object_path(path),
            content=data,
            headers={"Content-Type": content_type, "x-upsert": "true" if upsert else "false"},
        )

    def download(self, path: str) -> bytes:
        return self._request("GET", f"/object/authenticated/{self.bucket}/{quote(path)}").content

    def delete(self, paths: list[str]) -> None:
        if paths:
            self._request("DELETE", f"/object/{self.bucket}", json={"prefixes": paths})

    def signed_urls(self, paths: list[str], expires_in: int) -> dict[str, str]:
        """複数の画像の署名付き URL を1回の通信でまとめて作る(N+1 回の通信を避ける)。"""
        if not paths:
            return {}
        response = self._request(
            "POST",
            f"/object/sign/{self.bucket}",
            json={"expiresIn": expires_in, "paths": paths},
        )
        return {
            item["path"]: f"{self.base_url}{item['signedURL']}"
            for item in response.json()
            if item.get("signedURL")
        }

    def signed_upload_url(self, path: str) -> str:
        """ブラウザが直接アップロードするための、期限付きの URL を作る(9-7)。"""
        response = self._request("POST", f"/object/upload/sign/{self.bucket}/{quote(path)}")
        url: str = response.json()["url"]
        return f"{self.base_url}{url}"


def get_storage(request: Request) -> StorageClient:
    """lifespan で作ったストレージのクライアントを返す。"""
    storage: StorageClient = request.app.state.storage
    return storage


StorageDep = Annotated[StorageClient, Depends(get_storage)]
