from fastapi.testclient import TestClient

from app.main import app


def test_docs_returns_html():
    response = TestClient(app).get("/docs")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_openapi_schema_contains_api_title_and_tags():
    response = TestClient(app).get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "EstudaUnB API"

    tags = {tag["name"] for tag in schema["tags"]}
    assert {
        "health",
        "disciplines",
        "assessments",
        "attendance",
        "academic-simulation",
    }.issubset(tags)
