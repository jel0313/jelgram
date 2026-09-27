"""ヘルスチェック・CORS のテスト(詳細設計書 7.2 T-01〜T-03)。"""

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    """T-01: 認証ヘッダーなしで 200 と {"status": "ok"} が返る。"""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cors_preflight_from_allowed_origin(client: TestClient) -> None:
    """T-02: 許可したオリジンからのプリフライトが通る。"""
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_not_allowed_for_unknown_origin(client: TestClient) -> None:
    """T-03: 許可していないオリジンには CORS 許可のヘッダーを返さない。"""
    response = client.get("/health", headers={"Origin": "http://evil.example.com"})

    assert "access-control-allow-origin" not in response.headers
