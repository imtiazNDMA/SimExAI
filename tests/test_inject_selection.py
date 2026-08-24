"""Wing targeting and prompt selection for scenario injects."""
import logging

from backend import app as app_module
from backend.llm_engine import LLMEngine
from backend.scenario_engine import PHASES, ScenarioEngine
from test_session_api import CONTROLLER_ID, bootstrap, session_headers


def make_inject(
    inject_id: str,
    *,
    severity: str = "MEDIUM",
    wings: list[str] | None = None,
    description: str = "Exercise update.",
) -> dict:
    return {
        "id": inject_id,
        "phase_id": "d_minus_90",
        "time_offset": "H+1HRS",
        "title": inject_id.replace("_", " ").title(),
        "description": description,
        "severity": severity,
        "required_wings": wings or [],
    }


def test_normalize_injects_drops_and_logs_unknown_wings(caplog):
    caplog.set_level(logging.WARNING)

    injects = app_module._normalize_injects(
        [
            make_inject(
                "incoming",
                wings=["Ops & Log", "invented_coordination_wing"],
            ),
            make_inject("invalid_only", wings=["imaginary_wing"]),
        ],
        "scenario-a",
    )

    assert len(injects) == 1
    assert injects[0]["required_wings"] == ["operations_logistic"]
    assert "invented_coordination_wing" in caplog.text
    assert "Dropped inject scenario-a_inj_002" in caplog.text


def test_scenario_engine_filters_targeted_injects_but_keeps_global_ones():
    scenario = ScenarioEngine()
    scenario.injects_data = {
        "injects": [
            make_inject("ops", wings=["operations_logistic"]),
            make_inject("plans", wings=["plans"]),
            make_inject("global"),
        ]
    }

    selected = scenario.get_injects_for_phase("d_minus_90", "operations_logistic")

    assert [inject["id"] for inject in selected] == ["ops", "global"]
    assert [inject["id"] for inject in scenario.get_injects_for_phase("d_minus_90")] == [
        "global"
    ]


def test_inject_endpoint_returns_only_the_selected_wings_injects(client):
    session = bootstrap(client, CONTROLLER_ID).json()
    app_module.save_scenario({"id": "targeted", "name": "Targeted scenario"})
    app_module.save_injects(
        "targeted",
        [
            make_inject("ops", wings=["operations_logistic"]),
            make_inject("plans", wings=["plans"]),
            make_inject("global"),
        ],
    )
    app_module.update_exercise(
        session["exercise_id"], scenario_id="targeted", injects_id="targeted_injects"
    )

    unbound = client.get("/api/injects", headers=session_headers(CONTROLLER_ID))
    response = client.get(
        "/api/injects?wing_id=operations_logistic",
        headers=session_headers(CONTROLLER_ID),
    )

    assert [inject["title"] for inject in unbound.json()["injects"]] == ["Global"]
    assert response.status_code == 200
    assert [inject["title"] for inject in response.json()["injects"]] == [
        "Ops",
        "Global",
    ]
    assert bootstrap(client, CONTROLLER_ID).json()["wing_id"] is None


def test_prompt_ranks_targeted_injects_and_uses_a_token_budget():
    scenario = ScenarioEngine()
    scenario.scenario_data = {"name": "Selection exercise", "type": "Flood"}
    scenario.injects_data = {
        "injects": [
            make_inject("plans_critical", severity="CRITICAL", wings=["plans"]),
            make_inject("ops_high_low_score", severity="HIGH", wings=["operations_logistic"]),
            make_inject("ops_low", severity="LOW", wings=["operations_logistic"]),
            make_inject("ops_high_high_score", severity="HIGH", wings=["operations_logistic"]),
            make_inject("global_critical", severity="CRITICAL"),
            make_inject("ops_medium_1", wings=["operations_logistic"]),
            make_inject("ops_medium_2", wings=["operations_logistic"]),
            make_inject("ops_medium_3", wings=["operations_logistic"]),
        ]
    }
    responder = LLMEngine(scenario)
    prompt = responder._build_user_prompt(
        "operations_logistic",
        responder.get_wing_name("operations_logistic"),
        PHASES[0],
        "What changed?",
        retrieved_chunks=[
            {"id": f"scenario_{i}", "score": 1 - i / 10, "text": f"scenario {i}"}
            for i in range(5)
        ] + [
            {"id": "ops_high_low_score", "score": 0.2, "text": "low relevance"},
            {"id": "ops_high_high_score", "score": 0.9, "text": "high relevance"},
        ],
    )

    inject_section = prompt.split("Current injects relevant to this wing:\n", 1)[1]
    inject_section = inject_section.split("\nParticipant message", 1)[0]
    assert "Plans Critical" not in inject_section
    assert "Ops Medium 3" in inject_section  # no arbitrary six-item cutoff
    assert inject_section.index("Global Critical") < inject_section.index("Ops High High Score")
    assert inject_section.index("Ops High High Score") < inject_section.index("Ops High Low Score")
    assert "high relevance" not in prompt

    scenario.injects_data = {
        "injects": [
            make_inject(
                "oversized_critical",
                severity="CRITICAL",
                wings=["operations_logistic"],
                description="x" * 8000,
            ),
            make_inject("tail_low", severity="LOW", wings=["operations_logistic"]),
        ]
    }
    budgeted_prompt = responder._build_user_prompt(
        "operations_logistic",
        responder.get_wing_name("operations_logistic"),
        PHASES[0],
        "Status",
    )
    budgeted_section = budgeted_prompt.split(
        "Current injects relevant to this wing:\n", 1
    )[1].split("\nParticipant message", 1)[0]

    assert len(budgeted_section) <= 4900
    assert "Tail Low" not in budgeted_section

    packed = responder._format_inject_context(
        [
            make_inject("short_critical", severity="CRITICAL"),
            make_inject("oversized_high", severity="HIGH", description="y" * 1000),
            make_inject("short_low", severity="LOW"),
        ],
        token_budget=40,
    )
    assert "Short Critical" in packed
    assert "Oversized High" not in packed
    assert "Short Low" in packed


def test_rag_context_drops_injects_for_other_wings():
    scenario = ScenarioEngine()
    scenario.scenario_id = "rag-filtering"
    scenario.scenario_data = {"name": "RAG filtering", "type": "Flood"}
    future_inject = make_inject("future_ops_hit", wings=["operations_logistic"])
    future_inject["phase_id"] = "d_plus_90"
    scenario.injects_data = {
        "injects": [
            make_inject("ops_hit", wings=["operations_logistic"]),
            make_inject("plans_hit", wings=["plans"]),
            future_inject,
        ]
    }
    responder = LLMEngine(scenario)

    class FakeVectorStore:
        top_k = None

        def retrieve(self, query, scenario_id, top_k):
            self.top_k = top_k
            return [
                {"id": "plans_hit", "score": 0.99, "text": "plans secret"},
                {"id": "future_ops_hit", "score": 0.95, "text": "future spoiler"},
                {"id": "ops_hit", "score": 0.8, "text": "operations update"},
                {"id": "scenario_chunk", "score": 0.7, "text": "shared scenario"},
            ]

    class CaptureLLM:
        messages = None

        def invoke(self, messages):
            self.messages = messages

            class Result:
                content = "Continue."

            return Result()

    vector_store = FakeVectorStore()
    llm = CaptureLLM()
    responder.set_vector_store(vector_store)
    responder.llm = llm

    responder.get_response("operations_logistic", "d_minus_90", "Status")

    prompt = llm.messages[-1].content
    assert vector_store.top_k == 30
    assert "operations update" in prompt
    assert "shared scenario" in prompt
    assert "plans secret" not in prompt
    assert "future spoiler" not in prompt
