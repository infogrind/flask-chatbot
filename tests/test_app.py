from app import create_app


def test_health_endpoint() -> None:
    app = create_app()
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
