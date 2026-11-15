from app import app


def test_home_uses_application_urls(monkeypatch):
    monkeypatch.setenv("ODOO_URL", "https://odoo.example.com/")
    monkeypatch.setenv("PGADMIN_URL", "https://pgadmin.example.com/")
    response = app.test_client().get("/")
    assert response.status_code == 200
    assert b'https://odoo.example.com/' in response.data
    assert b'https://pgadmin.example.com/' in response.data


def test_version(monkeypatch):
    monkeypatch.setenv("APP_VERSION", "1.0")
    data = app.test_client().get("/api/info").get_json()
    assert data["version"] == "1.0"
    assert data["app"] == "legeni-academy"


def test_health():
    assert app.test_client().get("/health").get_json() == {"status": "ok"}


def test_static_css():
    assert app.test_client().get("/static/CSS/style.css").status_code == 200
