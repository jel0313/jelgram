"""Web Push の送信(11-7)。ブラウザ標準の仕組みで、無料で使える。

VAPID の鍵が未設定なら、送ったことにしてログだけ出す(開発中)。
"""

import json
import logging
from typing import Any

from pywebpush import WebPushException, webpush

logger = logging.getLogger(__name__)


class LogPushSender:
    """開発用:送らずにログに出す。"""

    def send(self, subscription: dict[str, Any], payload: dict[str, Any]) -> bool:
        logger.info("プッシュ通知(未送信。VAPID 未設定)", extra={"title": payload.get("title")})
        return True


class WebPushSender:
    def __init__(self, private_key: str, subject: str) -> None:
        self.private_key = private_key
        self.subject = subject

    def send(self, subscription: dict[str, Any], payload: dict[str, Any]) -> bool:
        try:
            webpush(
                subscription_info={
                    "endpoint": subscription["endpoint"],
                    "keys": {"p256dh": subscription["p256dh"], "auth": subscription["auth"]},
                },
                data=json.dumps(payload, ensure_ascii=False),
                vapid_private_key=self.private_key,
                vapid_claims={"sub": self.subject},
                timeout=10,
            )
        except WebPushException as e:
            status = getattr(e.response, "status_code", None)
            if status in (404, 410):  # 端末側で購読が解除された
                return False
            raise
        return True
