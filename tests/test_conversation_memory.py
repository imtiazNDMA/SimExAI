"""Phase 2 — conversation memory behavior at the HTTP boundary."""
import threading
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from backend import app as app_module
from backend import database
from backend.llm_engine import LLMEngine

from test_session_api import CONTROLLER_ID, PARTICIPANT_ID, bootstrap, session_headers


class RecordingLLM:
    """Stands in for ChatOpenAI, capturing the exact message list it receives."""

    def __init__(self):
        self.calls = []
        self.reply = "Understood. Proceed."

    def invoke(self, messages):
        self.calls.append(list(messages))

        class Result:
            content = self.reply

        return Result()


def install_recording_responder(monkeypatch, recorder: RecordingLLM):
    def build(scenario):
        engine = LLMEngine(scenario)
        engine.llm = recorder
        return engine

    monkeypatch.setattr(app_module, "_build_responder", build)


def chat(client: TestClient, message: str, session_id: str = CONTROLLER_ID):
    return client.post(
        "/api/chat",
        headers=session_headers(session_id),
        json={"wing_id": "operations_logistic", "message": message},
    )


def test_chat_persists_each_turn_and_passes_history_to_the_responder(
    client: TestClient, monkeypatch
):
    recorder = RecordingLLM()
    install_recording_responder(monkeypatch, recorder)
    bootstrap(client, CONTROLLER_ID)

    first = chat(client, "First message")
    assert first.status_code == 200
    with database.get_connection() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages ORDER BY id"
        ).fetchall()
    assert [(r["role"], r["content"]) for r in rows] == [
        ("user", "First message"),
        ("assistant", recorder.reply),
    ]

    second = chat(client, "Second message")
    assert second.status_code == 200

    prompt_messages = recorder.calls[1]
    assert len(prompt_messages) == 4
    assert prompt_messages[0].type == "system"
    assert prompt_messages[1].type == "human"
    assert prompt_messages[1].content == "First message"
    assert prompt_messages[2].type == "ai"
    assert prompt_messages[2].content == recorder.reply
    assert prompt_messages[3].type == "human"
    assert "Second message" in prompt_messages[3].content


def test_history_is_windowed_into_a_condensed_block_and_recent_turns(
    client: TestClient, monkeypatch
):
    recorder = RecordingLLM()
    install_recording_responder(monkeypatch, recorder)
    bootstrap(client, CONTROLLER_ID)

    with database.get_connection() as conn:
        for i in range(20):
            conn.execute(
                "INSERT INTO messages (session_id, role, content, wing_id, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    CONTROLLER_ID,
                    "user" if i % 2 == 0 else "assistant",
                    f"old turn number {i} with padding to exceed the truncation length",
                    "operations_logistic",
                    "2026-01-01T00:00:00",
                ),
            )

    chat(client, "Latest message")

    prompt_messages = recorder.calls[0]
    condensed = [m for m in prompt_messages if "Earlier conversation summary" in m.content]
    history_turns = [
        m for m in prompt_messages[:-1]
        if m.type in ("human", "ai")
    ]
    assert len(condensed) == 1
    assert len(history_turns) == 12
    assert any("old turn number 19" in m.content for m in prompt_messages)


def test_transcript_can_be_restored_over_http(client: TestClient, monkeypatch):
    install_recording_responder(monkeypatch, RecordingLLM())
    bootstrap(client, CONTROLLER_ID)
    chat(client, "Hello")
    chat(client, "What is my status?")

    response = client.get("/api/session/messages", headers=session_headers(CONTROLLER_ID))

    assert response.status_code == 200
    messages = response.json()["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]
    assert [m["content"] for m in messages[:2]] == ["Hello", "Understood. Proceed."]
    assert all(m["wing_id"] == "operations_logistic" for m in messages)


def test_phase_briefing_persists_only_the_moderator_response(
    client: TestClient, monkeypatch
):
    recorder = RecordingLLM()
    install_recording_responder(monkeypatch, recorder)
    bootstrap(client, CONTROLLER_ID)
    advanced = client.post(
        "/api/phase/advance", headers=session_headers(CONTROLLER_ID)
    )

    response = client.post(
        "/api/wings/technical_early_warning/phase-briefing",
        headers=session_headers(CONTROLLER_ID),
    )

    assert advanced.status_code == 200
    assert response.status_code == 200
    assert response.json()["phase_id"] == "d_minus_30"
    messages = client.get(
        "/api/session/messages", headers=session_headers(CONTROLLER_ID)
    ).json()["messages"]
    assert [(message["role"], message["kind"]) for message in messages] == [
        ("assistant", "phase_briefing")
    ]
    assert all("Phase advancement notice" not in message["content"] for message in messages)
    assert "Turn objective (phase_briefing)" in recorder.calls[0][-1].content
    assert "Participant message:\nThe authoritative exercise timeline is now D-30" in (
        recorder.calls[0][-1].content
    )


def test_phase_briefing_excludes_future_phase_history_after_reset(
    client: TestClient, monkeypatch
):
    recorder = RecordingLLM()
    install_recording_responder(monkeypatch, recorder)
    bootstrap(client, CONTROLLER_ID)
    database.save_message(
        CONTROLLER_ID,
        "user",
        "Future D-Day field operation detail",
        phase_id="d_day",
        wing_id="technical_early_warning",
    )
    client.post("/api/phase/reset", headers=session_headers(CONTROLLER_ID))

    response = client.post(
        "/api/wings/technical_early_warning/phase-briefing",
        headers=session_headers(CONTROLLER_ID),
    )

    assert response.status_code == 200
    assert not any(
        "Future D-Day field operation detail" in message.content
        for message in recorder.calls[0]
    )


def test_phase_change_during_generation_discards_stale_briefing(
    client: TestClient, monkeypatch
):
    started = threading.Event()
    release = threading.Event()

    class BlockingLLM(RecordingLLM):
        def invoke(self, messages):
            started.set()
            assert release.wait(timeout=5)
            return super().invoke(messages)

    install_recording_responder(monkeypatch, BlockingLLM())
    bootstrap(client, CONTROLLER_ID)

    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(
            client.post,
            "/api/wings/technical_early_warning/phase-briefing",
            headers=session_headers(CONTROLLER_ID),
        )
        assert started.wait(timeout=5)
        advanced = client.post(
            "/api/phase/advance", headers=session_headers(CONTROLLER_ID)
        )
        release.set()
        response = pending.result(timeout=5)

    assert advanced.status_code == 200
    assert response.status_code == 200
    assert response.json()["discarded"] is True
    assert response.json()["discard_reason"] == "phase_changed"
    assert client.get(
        "/api/session/messages", headers=session_headers(CONTROLLER_ID)
    ).json()["messages"] == []


def test_clear_chat_deletes_only_the_selected_session_wing_and_is_idempotent(
    client: TestClient, monkeypatch
):
    recorder = RecordingLLM()
    install_recording_responder(monkeypatch, recorder)
    bootstrap(client, CONTROLLER_ID)
    bootstrap(client, PARTICIPANT_ID)

    chat(client, "Operations history")
    client.post(
        "/api/chat",
        headers=session_headers(CONTROLLER_ID),
        json={"wing_id": "plans", "message": "Plans history"},
    )
    database.save_message(
        PARTICIPANT_ID,
        "user",
        "Other session history",
        wing_id="operations_logistic",
    )
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO messages (session_id, role, content, wing_id, kind, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                CONTROLLER_ID,
                "assistant",
                "Retained assessment result",
                "operations_logistic",
                "assessment_result",
                "2026-01-01T00:00:00",
            ),
        )
        conn.execute(
            "INSERT INTO messages (session_id, role, content, wing_id, created_at)"
            " VALUES (?, ?, ?, NULL, ?)",
            (
                CONTROLLER_ID,
                "user",
                "Legacy unscoped history",
                "2026-01-01T00:00:00",
            ),
        )
        conn.execute(
            "INSERT INTO inject_state (session_id, inject_id, status) VALUES (?, ?, ?)",
            (CONTROLLER_ID, "retained-inject", "addressed"),
        )
        conn.execute(
            "INSERT INTO assessments (session_id, scores, created_at) VALUES (?, ?, ?)",
            (CONTROLLER_ID, '{"score": 8}', "2026-01-01T00:00:00"),
        )

    cleared = client.delete(
        "/api/session/messages/operations_logistic",
        headers=session_headers(CONTROLLER_ID),
    )
    repeated = client.delete(
        "/api/session/messages/operations_logistic",
        headers=session_headers(CONTROLLER_ID),
    )

    assert cleared.status_code == 200
    assert cleared.json() == {"wing_id": "operations_logistic", "deleted_count": 2}
    assert repeated.status_code == 200
    assert repeated.json()["deleted_count"] == 0

    transcript = client.get(
        "/api/session/messages", headers=session_headers(CONTROLLER_ID)
    ).json()["messages"]
    plans_messages = [message for message in transcript if message["wing_id"] == "plans"]
    assert [message["content"] for message in plans_messages] == [
        "Plans history",
        recorder.reply,
    ]
    assert any(
        message["content"] == "Retained assessment result"
        and message["kind"] == "assessment_result"
        for message in transcript
    )
    assert any(message["content"] == "Legacy unscoped history" for message in transcript)
    other_transcript = client.get(
        "/api/session/messages", headers=session_headers(PARTICIPANT_ID)
    ).json()["messages"]
    assert [message["content"] for message in other_transcript] == ["Other session history"]
    with database.get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM assessments").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM inject_state").fetchone()[0] == 1

    chat(client, "Fresh operations turn")
    latest_prompt = recorder.calls[-1]
    assert not any("Operations history" in message.content for message in latest_prompt)
    assert not any("Plans history" in message.content for message in latest_prompt)
    assert not any("Legacy unscoped history" in message.content for message in latest_prompt)
    assert not any("Retained assessment result" in message.content for message in latest_prompt)


def test_clear_during_generation_discards_the_stale_assistant_response(
    client: TestClient, monkeypatch
):
    started = threading.Event()
    release = threading.Event()

    class BlockingLLM(RecordingLLM):
        def invoke(self, messages):
            started.set()
            assert release.wait(timeout=5)
            return super().invoke(messages)

    install_recording_responder(monkeypatch, BlockingLLM())
    bootstrap(client, CONTROLLER_ID)

    with ThreadPoolExecutor(max_workers=1) as pool:
        pending_chat = pool.submit(chat, client, "Message being processed")
        assert started.wait(timeout=5)
        cleared = client.delete(
            "/api/session/messages/operations_logistic",
            headers=session_headers(CONTROLLER_ID),
        )
        release.set()
        response = pending_chat.result(timeout=5)

    assert cleared.status_code == 200
    assert response.status_code == 200
    assert response.json()["discarded"] is True
    assert response.json()["discard_reason"] == "history_cleared"
    transcript = client.get(
        "/api/session/messages", headers=session_headers(CONTROLLER_ID)
    ).json()["messages"]
    assert transcript == []


def test_participant_can_clear_only_its_bound_wing(client: TestClient, monkeypatch):
    install_recording_responder(monkeypatch, RecordingLLM())
    bootstrap(client, CONTROLLER_ID)
    chat(client, "Operations history")
    with database.get_connection() as conn:
        conn.execute(
            "UPDATE sessions SET role = 'participant', wing_id = ? WHERE id = ?",
            ("operations_logistic", CONTROLLER_ID),
        )

    forbidden = client.delete(
        "/api/session/messages/plans", headers=session_headers(CONTROLLER_ID)
    )
    allowed = client.delete(
        "/api/session/messages/operations_logistic",
        headers=session_headers(CONTROLLER_ID),
    )

    assert forbidden.status_code == 403
    assert allowed.status_code == 200
    assert allowed.json()["deleted_count"] == 2


def test_clear_chat_rejects_unknown_wing(client: TestClient, monkeypatch):
    install_recording_responder(monkeypatch, RecordingLLM())
    bootstrap(client, CONTROLLER_ID)

    response = client.delete(
        "/api/session/messages/not-a-wing", headers=session_headers(CONTROLLER_ID)
    )

    assert response.status_code == 400


def test_inject_ledger_reports_delivered_and_addressed(client: TestClient, monkeypatch):
    recorder = RecordingLLM()
    install_recording_responder(monkeypatch, recorder)
    session = bootstrap(client, CONTROLLER_ID).json()

    database.save_scenario(
        {
            "id": "scen-ledger",
            "name": "Ledger scenario",
            "type": "Flood",
            "magnitude": "Severe",
        }
    )
    database.save_injects(
        "scen-ledger",
        [
            {
                "id": "inj_a",
                "phase_id": "d_minus_90",
                "time_offset": "H+1HRS",
                "title": "River flooding at Sutlej",
                "description": "Flooding observed along the river.",
                "severity": "HIGH",
                "target_wings": ["operations_logistic"],
                "response_required": True,
            },
            {
                "id": "inj_b",
                "phase_id": "d_minus_90",
                "time_offset": "H+4HRS",
                "title": "Evacuation of low-lying settlements",
                "description": "Move residents to higher ground.",
                "severity": "CRITICAL",
                "target_wings": ["operations_logistic"],
                "response_required": True,
            },
        ],
    )
    database.update_exercise(
        session["exercise_id"],
        scenario_id="scen-ledger",
        injects_id="scen-ledger_injects",
    )

    chat(client, "How should we handle River flooding at Sutlej?")

    with database.get_connection() as conn:
        states = {
            row["inject_id"]: row["status"]
            for row in conn.execute(
                "SELECT inject_id, status FROM inject_state WHERE session_id = ?",
                (CONTROLLER_ID,),
            ).fetchall()
        }

    assert len(states) == 2
    assert states["scen-ledger_inj_a"] == "addressed"
    assert states["scen-ledger_inj_b"] == "delivered"

    user_prompt = recorder.calls[0][-1].content
    assert "Inject status ledger" in user_prompt
    assert "[delivered]" in user_prompt
    assert "[addressed]" in user_prompt
