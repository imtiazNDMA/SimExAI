"""Uniform session access and persistence behavior at the HTTP boundary."""
import pytest
from fastapi.testclient import TestClient

from backend import app as app_module
from backend import database


CONTROLLER_ID = "11111111-1111-4111-8111-111111111111"
PARTICIPANT_ID = "22222222-2222-4222-8222-222222222222"


def session_headers(session_id: str) -> dict[str, str]:
    return {"X-Session-Id": session_id}


def bootstrap(client: TestClient, session_id: str):
    return client.post("/api/session", headers=session_headers(session_id))


def test_sessions_share_exercise_phase_and_have_uniform_control(client: TestClient):
    first_session = bootstrap(client, CONTROLLER_ID)
    second_session = bootstrap(client, PARTICIPANT_ID)

    assert first_session.status_code == 200
    assert first_session.json()["role"] == "controller"
    assert second_session.status_code == 200
    assert second_session.json()["role"] == "controller"
    assert second_session.json()["exercise_id"] == first_session.json()["exercise_id"]

    database.save_scenario({"id": "scenario-1", "name": "Persistent scenario"})
    database.update_exercise(
        first_session.json()["exercise_id"],
        scenario_id="scenario-1",
        injects_id="scenario-1-injects",
    )

    advanced = client.post("/api/phase/advance", headers=session_headers(PARTICIPANT_ID))
    assert advanced.status_code == 200
    assert advanced.json()["current_phase"]["id"] == "d_minus_30"

    first_view = client.get("/api/phases", headers=session_headers(CONTROLLER_ID))
    active_phase = next(phase for phase in first_view.json()["phases"] if phase["is_active"])
    assert active_phase["id"] == "d_minus_30"

    reset = client.post("/api/phase/reset", headers=session_headers(CONTROLLER_ID))
    assert reset.status_code == 200
    assert reset.json()["scenario"]["id"] == "scenario-1"
    assert next(phase for phase in reset.json()["phases"] if phase["is_active"])["id"] == "d_minus_90"


def test_session_header_is_required_and_unknown_sessions_are_rejected(client: TestClient):
    requests_without_session = (
        ("get", "/api/scenario", {}),
        ("get", "/api/phases", {}),
        ("get", "/api/wings", {}),
        ("get", "/api/wings/operations_logistic/actions", {}),
        ("get", "/api/injects", {}),
        ("delete", "/api/session/messages/operations_logistic", {}),
        ("post", "/api/wings/operations_logistic/phase-briefing", {}),
        ("get", "/api/scenario/upload/unknown", {}),
        ("post", "/api/phase/advance", {}),
        ("post", "/api/phase/back", {}),
        ("post", "/api/phase/reset", {}),
        ("post", "/api/chat", {"json": {"wing_id": "operations_logistic", "message": "Hi"}}),
        ("post", "/api/tts", {"json": {"text": "Hi"}}),
        ("post", "/api/scenario/upload", {"files": {"file": ("scenario.txt", b"test")}}),
    )
    for method, path, kwargs in requests_without_session:
        missing = getattr(client, method)(path, **kwargs)
        assert missing.status_code == 400, path

    unknown = client.get(
        "/api/phases",
        headers=session_headers("33333333-3333-4333-8333-333333333333"),
    )

    assert unknown.status_code == 404


def test_bootstrap_is_idempotent(client: TestClient):
    first = bootstrap(client, CONTROLLER_ID)
    second = bootstrap(client, CONTROLLER_ID)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["role"] == "controller"


def test_chat_uses_server_authoritative_phase(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    observed = {}

    class FakeResponder:
        @staticmethod
        def normalize_wing_id(wing_id):
            return wing_id

        @staticmethod
        def get_wing_name(_wing_id):
            return "Operations Wing"

        @staticmethod
        def get_response(wing_id, phase_id, user_message, history=None, inject_ledger=None):
            observed.update(wing_id=wing_id, phase_id=phase_id, message=user_message)
            return "Continue the exercise."

    monkeypatch.setattr(app_module, "_build_responder", lambda _scenario: FakeResponder())
    bootstrap(client, CONTROLLER_ID)

    response = client.post(
        "/api/chat",
        headers=session_headers(CONTROLLER_ID),
        json={
            "wing_id": "operations_logistic",
            "phase_id": "d_plus_90",
            "message": "What should we do?",
        },
    )

    assert response.status_code == 200
    assert observed["phase_id"] == "d_minus_90"


def test_every_session_can_switch_wings(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    class FakeResponder:
        KNOWN_WINGS = {"operations_logistic", "plans"}

        @staticmethod
        def normalize_wing_id(wing_id):
            return wing_id if wing_id in FakeResponder.KNOWN_WINGS else None

        @staticmethod
        def get_wing_name(wing_id):
            return wing_id

        @staticmethod
        def get_response(**_kwargs):
            return "Continue."

        @staticmethod
        def get_wing_actions(_wing_id, _phase_id):
            return []

    monkeypatch.setattr(app_module, "_build_responder", lambda _scenario: FakeResponder())
    bootstrap(client, CONTROLLER_ID)
    bootstrap(client, PARTICIPANT_ID)

    bogus = client.post(
        "/api/chat",
        headers=session_headers(PARTICIPANT_ID),
        json={"wing_id": "not_a_wing", "message": "Status"},
    )
    first_wing = client.post(
        "/api/chat",
        headers=session_headers(PARTICIPANT_ID),
        json={"wing_id": "operations_logistic", "message": "Status"},
    )
    other_wing = client.post(
        "/api/chat",
        headers=session_headers(PARTICIPANT_ID),
        json={"wing_id": "plans", "message": "Status"},
    )
    other_actions = client.get(
        "/api/wings/plans/actions", headers=session_headers(PARTICIPANT_ID)
    )

    assert bogus.status_code == 400
    assert first_wing.status_code == 200
    assert other_wing.status_code == 200
    assert other_actions.status_code == 200
    assert bootstrap(client, PARTICIPANT_ID).json()["wing_id"] == "plans"


def test_inactive_session_is_replaced_by_a_new_controller(client: TestClient):
    bootstrap(client, CONTROLLER_ID)
    with database.get_connection() as conn:
        conn.execute("UPDATE sessions SET status = 'inactive' WHERE id = ?", (CONTROLLER_ID,))

    inactive = bootstrap(client, CONTROLLER_ID)
    replacement = bootstrap(client, PARTICIPANT_ID)

    assert inactive.status_code == 409
    assert replacement.status_code == 200
    assert replacement.json()["role"] == "controller"


def test_upload_jobs_are_visible_only_to_the_owner(client: TestClient):
    first_session = bootstrap(client, CONTROLLER_ID).json()
    bootstrap(client, PARTICIPANT_ID)
    app_module._upload_jobs["private-job"] = {
        "job_id": "private-job",
        "session_id": CONTROLLER_ID,
        "exercise_id": first_session["exercise_id"],
        "started_at": 0,
        "updated_at": 0,
    }

    other_session = client.get(
        "/api/scenario/upload/private-job", headers=session_headers(PARTICIPANT_ID)
    )
    owner = client.get(
        "/api/scenario/upload/private-job", headers=session_headers(CONTROLLER_ID)
    )

    assert other_session.status_code == 404
    assert owner.status_code == 200
    assert "session_id" not in owner.json()
    assert "exercise_id" not in owner.json()
