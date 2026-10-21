"""メール送信(11-3)。

API の応答を待たせないよう、FastAPI の BackgroundTasks で「応答を返した後」に送る。
    リクエスト → 処理 → 応答を返す → (その後)メール送信
失敗しても利用者の操作は成功扱い。ログに残すだけにする。
開発中は Supabase のローカル環境に入っている Mailpit(http://127.0.0.1:54324)で受信を確認できる。
"""

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import Settings

logger = logging.getLogger(__name__)


def send_email(settings: Settings, *, to: str, subject: str, body: str) -> None:
    if not settings.smtp_host:
        logger.info("SMTP が未設定のため、メールを送りませんでした", extra={"subject": subject})
        return
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.send_message(message)
        logger.info("メールを送りました", extra={"subject": subject})
    except (OSError, smtplib.SMTPException):
        logger.exception("メールを送れませんでした", extra={"subject": subject})
