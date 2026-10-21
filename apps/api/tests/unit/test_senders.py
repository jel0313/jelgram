"""UT:メール送信(11-3)・Web Push(11-7)。外部への送信は差し替える。"""

from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

from app.core import email
from app.core.config import get_settings
from app.worker import push


class FakeSMTP:
    sent: ClassVar[list[Any]] = []
    fail = False

    def __init__(self, host: str, port: int, timeout: int) -> None:
        self.address = (host, port)

    def __enter__(self) -> "FakeSMTP":
        if FakeSMTP.fail:
            raise OSError("接続できない")
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def send_message(self, message: Any) -> None:
        FakeSMTP.sent.append(message)


@pytest.fixture
def smtp(monkeypatch: pytest.MonkeyPatch) -> type[FakeSMTP]:
    FakeSMTP.sent = []
    FakeSMTP.fail = False
    monkeypatch.setattr(email.smtplib, "SMTP", FakeSMTP)
    return FakeSMTP


class TestSendEmail:
    def test_sends(self, smtp: type[FakeSMTP]) -> None:
        settings = get_settings().model_copy(update={"smtp_host": "mail.test"})
        email.send_email(settings, to="a@example.com", subject="件名", body="本文")
        assert smtp.sent[0]["To"] == "a@example.com" and smtp.sent[0]["Subject"] == "件名"

    def test_not_configured(self, smtp: type[FakeSMTP]) -> None:
        email.send_email(get_settings(), to="a@example.com", subject="s", body="b")
        assert smtp.sent == []

    def test_failure_is_only_logged(
        self, smtp: type[FakeSMTP], caplog: pytest.LogCaptureFixture
    ) -> None:
        """送れなくても例外にしない(利用者の操作は成功のまま)。"""
        smtp.fail = True
        settings = get_settings().model_copy(update={"smtp_host": "mail.test"})
        email.send_email(settings, to="a@example.com", subject="s", body="b")
        assert "メールを送れませんでした" in caplog.text


SUBSCRIPTION = {"endpoint": "https://push.test/x", "p256dh": "k", "auth": "a"}


class TestWebPush:
    def test_sends(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = []
        monkeypatch.setattr(push, "webpush", lambda **kwargs: calls.append(kwargs))
        assert push.WebPushSender("key", "mailto:a@b").send(SUBSCRIPTION, {"title": "t"}) is True
        assert calls[0]["subscription_info"]["endpoint"] == "https://push.test/x"
        assert calls[0]["vapid_claims"] == {"sub": "mailto:a@b"}

    @pytest.mark.parametrize(("status", "result"), [(404, False), (410, False)])
    def test_gone_subscription(
        self, monkeypatch: pytest.MonkeyPatch, status: int, result: bool
    ) -> None:
        """端末側で解除された宛先(404・410)は False(呼び出し元が削除する)。"""

        def fail(**kwargs: Any) -> None:
            raise push.WebPushException("gone", response=SimpleNamespace(status_code=status))

        monkeypatch.setattr(push, "webpush", fail)
        assert push.WebPushSender("key", "mailto:a@b").send(SUBSCRIPTION, {}) is result

    def test_other_errors_are_raised(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """一時的なエラーは例外にして、Outbox に再試行させる。"""

        def fail(**kwargs: Any) -> None:
            raise push.WebPushException("server error", response=SimpleNamespace(status_code=500))

        monkeypatch.setattr(push, "webpush", fail)
        with pytest.raises(push.WebPushException):
            push.WebPushSender("key", "mailto:a@b").send(SUBSCRIPTION, {})

    def test_log_sender(self) -> None:
        assert push.LogPushSender().send(SUBSCRIPTION, {"title": "t"}) is True
