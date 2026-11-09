import pytest


@pytest.mark.django_db
def test_openapi_schema_is_public_and_documents_core_operations(api_client):
    response = api_client.get("/api/schema")

    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/vnd.oai.openapi")
    assert response.data["openapi"].startswith("3.")
    assert "/api/todos" in response.data["paths"]
    assert "/api/auth/login" in response.data["paths"]
    assert "/api/categories" in response.data["paths"]
    assert response.data["components"]["securitySchemes"]["BearerAuth"] == {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path",
    ["/api/docs", "/api/redoc"],
)
def test_documentation_ui_pages_are_public(api_client, path):
    response = api_client.get(path)

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/html")
