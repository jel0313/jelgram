"""UT:画像の検証・加工・ストレージのクライアント・サービス(9章)。"""

import io
import json
from uuid import uuid4

import httpx2
import pytest
from PIL import Image

from app.media import repository, service
from app.media.exceptions import (
    BrokenImageError,
    ImageTooLargeError,
    MediaNotFoundError,
    UnsupportedImageError,
)
from app.media.processing import process_image
from app.media.storage import StorageError, SupabaseStorage
from app.media.validation import detect_content_type, validate_image
from tests.fakes import FakeStorage, make_image


class TestDetectContentType:
    @pytest.mark.parametrize(
        ("fmt", "expected"),
        [
            ("PNG", "image/png"),
            ("JPEG", "image/jpeg"),
            ("GIF", "image/gif"),
            ("WEBP", "image/webp"),
        ],
    )
    def test_detects_real_formats(self, fmt: str, expected: str) -> None:
        assert detect_content_type(make_image(fmt)[:16]) == expected

    def test_unknown(self) -> None:
        assert detect_content_type(b"%PDF-1.7 ....") is None


class TestValidateImage:
    def test_valid_png(self) -> None:
        image = validate_image(
            make_image("PNG", (40, 30)), filename="a.PNG", declared_type="image/png"
        )
        assert (image.content_type, image.extension, image.width, image.height) == (
            "image/png",
            "png",
            40,
            30,
        )

    def test_jpeg_extension_variants(self) -> None:
        data = make_image("JPEG")
        assert (
            validate_image(data, filename="a.jpeg", declared_type="image/jpeg").extension == "jpg"
        )

    def test_too_large(self) -> None:
        """境界値:5MB + 1 バイトは NG。"""
        with pytest.raises(ImageTooLargeError):
            validate_image(
                b"\x89PNG\r\n\x1a\n" + b"0" * (5 * 1024 * 1024 - 7),
                filename="a.png",
                declared_type=None,
            )

    def test_empty(self) -> None:
        with pytest.raises(BrokenImageError):
            validate_image(b"", filename="a.png", declared_type="image/png")

    def test_disguised_file_is_rejected(self) -> None:
        """拡張子と MIME を画像に見せかけた PDF。マジックバイトで見破る。"""
        with pytest.raises(UnsupportedImageError):
            validate_image(b"%PDF-1.7 fake", filename="a.png", declared_type="image/png")

    def test_declared_type_mismatch(self) -> None:
        with pytest.raises(UnsupportedImageError):
            validate_image(make_image("PNG"), filename="a.png", declared_type="image/jpeg")

    def test_extension_mismatch(self) -> None:
        with pytest.raises(UnsupportedImageError):
            validate_image(make_image("PNG"), filename="a.jpg", declared_type="image/png")

    def test_svg_is_rejected(self) -> None:
        """SVG はスクリプトを埋め込めるので許可しない。"""
        with pytest.raises(UnsupportedImageError):
            validate_image(
                b"<svg onload=alert(1)>", filename="a.svg", declared_type="image/svg+xml"
            )

    def test_truncated_image(self) -> None:
        data = make_image("PNG", (200, 200))
        with pytest.raises(BrokenImageError):
            validate_image(data[:60], filename="a.png", declared_type="image/png")

    def test_pixel_bomb(self) -> None:
        """小さいファイルでも、縦横が巨大な画像は拒否する。"""
        data = make_image("PNG", (8000, 6000))
        with pytest.raises((ImageTooLargeError, BrokenImageError)):
            validate_image(data, filename="a.png", declared_type="image/png")


class TestProcessImage:
    def test_exif_is_removed_and_thumbnail_created(self) -> None:
        exif = Image.Exif()
        exif[0x010F] = "SecretCamera"  # メーカー名
        data = make_image("JPEG", (800, 600), exif=exif.tobytes())
        assert b"SecretCamera" in data

        processed = process_image(data, "image/jpeg")

        assert b"SecretCamera" not in processed.data
        assert (processed.width, processed.height) == (800, 600)
        thumb = Image.open(io.BytesIO(processed.thumbnail))
        assert thumb.format == "WEBP"
        assert max(thumb.size) == 320

    def test_gif_body_is_kept(self) -> None:
        data = make_image("GIF")
        assert process_image(data, "image/gif").data == data


def _storage(handler) -> SupabaseStorage:  # type: ignore[no-untyped-def]
    storage = SupabaseStorage(
        supabase_url="https://x.supabase.co", secret_key="sb_secret_x", bucket="media"
    )
    storage.http = httpx2.Client(
        base_url=storage.base_url,
        headers={"apikey": "sb_secret_x"},
        transport=httpx2.MockTransport(handler),
    )
    return storage


class TestSupabaseStorage:
    def test_upload_sends_key_and_type(self) -> None:
        seen: dict[str, str] = {}

        def handler(request: httpx2.Request) -> httpx2.Response:
            seen.update(
                url=str(request.url),
                key=request.headers["apikey"],
                type=request.headers["content-type"],
            )
            return httpx2.Response(200, json={"Key": "media/u/a.png"})

        _storage(handler).upload("u/a.png", b"data", "image/png")
        assert seen == {
            "url": "https://x.supabase.co/storage/v1/object/media/u/a.png",
            "key": "sb_secret_x",
            "type": "image/png",
        }

    def test_signed_urls_in_one_request(self) -> None:
        calls = []

        def handler(request: httpx2.Request) -> httpx2.Response:
            calls.append(json.loads(request.content))
            return httpx2.Response(
                200,
                json=[
                    {
                        "path": "a.png",
                        "signedURL": "/object/sign/media/a.png?token=t",
                        "error": None,
                    },
                    {"path": "b.png", "signedURL": None, "error": "not found"},
                ],
            )

        urls = _storage(handler).signed_urls(["a.png", "b.png"], 60)
        assert urls == {"a.png": "https://x.supabase.co/storage/v1/object/sign/media/a.png?token=t"}
        assert calls == [{"expiresIn": 60, "paths": ["a.png", "b.png"]}]

    def test_empty_paths_make_no_request(self) -> None:
        storage = _storage(lambda r: pytest.fail("呼ばれてはいけない"))  # type: ignore[arg-type,return-value]
        assert storage.signed_urls([], 60) == {}
        storage.delete([])

    def test_error_becomes_storage_error(self) -> None:
        with pytest.raises(StorageError):
            _storage(lambda r: httpx2.Response(500)).download("a.png")

    def test_signed_upload_url(self) -> None:
        storage = _storage(
            lambda r: httpx2.Response(200, json={"url": "/object/upload/sign/media/a.png?token=u"})
        )
        assert storage.signed_upload_url("a.png").endswith(
            "/storage/v1/object/upload/sign/media/a.png?token=u"
        )


class FakeSession:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class TestUploadService:
    def test_path_is_uuid_not_client_filename(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """保存名にクライアントのファイル名を使わない(9-4)。"""
        owner = uuid4()
        rows: list[dict] = []  # type: ignore[type-arg]

        def insert_media(session, **values):  # type: ignore[no-untyped-def]
            row = {
                **values,
                "id": uuid4(),
                "status": "pending",
                "thumbnail_path": None,
                "created_at": "2026-01-01T00:00:00Z",
            }
            rows.append(row)
            return row

        monkeypatch.setattr(repository, "insert_media", insert_media)
        monkeypatch.setattr(service.outbox, "enqueue", lambda *a, **k: None)
        storage = FakeStorage()
        session = FakeSession()

        result = service.upload_media(
            session,  # type: ignore[arg-type]
            storage,
            owner_id=owner,
            data=make_image("PNG"),
            filename="../../etc/passwd.png",
            content_type="image/png",
            expires_in=60,
        )

        (path,) = storage.objects
        assert path.startswith(f"{owner}/") and path.endswith(".png") and ".." not in path
        assert result.url is not None and session.committed

    def test_storage_file_is_removed_when_db_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """DB に登録できなければ、置いたファイルを消す(ストレージはロールバックできない)。"""

        def insert_media(session, **values):  # type: ignore[no-untyped-def]
            raise RuntimeError("DB error")

        monkeypatch.setattr(repository, "insert_media", insert_media)
        storage = FakeStorage()
        session = FakeSession()
        with pytest.raises(RuntimeError):
            service.upload_media(
                session,  # type: ignore[arg-type]
                storage,
                owner_id=uuid4(),
                data=make_image("PNG"),
                filename="a.png",
                content_type="image/png",
                expires_in=60,
            )
        assert storage.objects == {} and session.rolled_back

    def test_get_media_url_hidden_is_404(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """見る権限がない画像は 404(存在を教えない)。"""
        monkeypatch.setattr(repository, "get_visible_media", lambda *a: None)
        with pytest.raises(MediaNotFoundError):
            service.get_media_url(
                None, FakeStorage(), viewer_id=uuid4(), media_id=uuid4(), expires_in=60
            )  # type: ignore[arg-type]

    def test_sign_media_survives_storage_outage(self) -> None:
        storage = FakeStorage()
        storage.fail = True
        media_id = uuid4()
        signed = service.sign_media(storage, [{"id": media_id, "path": "a.png"}], 60)
        assert signed[media_id].url is None
