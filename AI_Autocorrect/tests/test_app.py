from types import SimpleNamespace


def test_index_renders_workspace(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Autocorrect Studio" in response.data


def test_preview_api_returns_structured_result(app_module, client, monkeypatch):
    monkeypatch.setattr(
        app_module.transformer_corrector,
        "correct",
        lambda *args, **kwargs: SimpleNamespace(
            corrected_text="Hello world.",
            confidence_score=90.0,
            model_name="stub-model",
            used_transformer=False,
            explanation="Stubbed transformer.",
            context_summary="",
        ),
    )
    monkeypatch.setattr(app_module, "analyze_spelling", lambda text, language: {"corrected_text": text, "issues": [], "confidence": 1.0})
    monkeypatch.setattr(app_module, "correct_grammar", lambda text, language: {"corrected_text": text, "issues": [], "confidence": 1.0})
    monkeypatch.setattr(app_module, "calculate_readability", lambda text: 88.0)
    monkeypatch.setattr(app_module, "analyze_sentiment", lambda text: {"label": "Neutral", "polarity": 0.0})
    monkeypatch.setattr(app_module, "extract_keywords", lambda text, language: ["hello", "world"])

    response = client.post("/api/preview", json={"text": "hello world", "language": "en", "context_before": ""})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["stored"] is False
    assert payload["corrected_text"] == "Hello world."
    assert payload["stats"]["confidence_score"] == 95.5


def test_register_and_history_access(client):
    register_response = client.post(
        "/auth/register",
        data={
            "full_name": "Ada Lovelace",
            "email": "ada@example.com",
            "password": "SecurePass123!",
            "confirm_password": "SecurePass123!",
        },
        follow_redirects=True,
    )

    assert register_response.status_code == 200

    history_response = client.get("/history")
    assert history_response.status_code == 200
    assert b"History center" in history_response.data


def test_admin_dashboard_requires_admin_login(app_module, client):
    login_response = client.post(
        "/auth/login",
        data={"email": "admin@example.com", "password": "Admin@12345!"},
        follow_redirects=True,
    )

    assert login_response.status_code == 200

    dashboard_response = client.get("/admin/dashboard")
    assert dashboard_response.status_code == 200
    assert b"Analytics dashboard" in dashboard_response.data