import pytest


@pytest.mark.django_db
def test_login_rate_limit_returns_429_and_retry_after(api_client):
    payload = {"email": "unknown@example.com", "password": "wrong-password"}

    responses = [
        api_client.post("/api/auth/login", payload, format="json") for _ in range(6)
    ]

    assert [response.status_code for response in responses[:5]] == [401] * 5
    limited = responses[5]
    assert limited.status_code == 429
    assert limited.data["code"] == 429
    assert "error" in limited.data
    assert int(limited["Retry-After"]) > 0
