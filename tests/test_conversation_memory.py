"""Phase 2 — conversation memory behavior at the HTTP boundary."""
from fastapi.testclient import TestClient

from backend import app as app_module
from backend import database
from backend.llm_engine import LLMEngine

from test_session_api import CONTROLLER_ID, bootstrap, session_headers


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
                "INSERT INTO messages (session_id, role, content, created_at)"
                " VALUES (?, ?, ?, ?)",
                (
                    CONTROLLER_ID,
                    "user" if i % 2 == 0 else "assistant",
                    f"old turn number {i} with padding to exceed the truncation length",
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