"""Prompt-level quality contract for natural, scenario-grounded moderation."""
from backend.llm_engine import LLMEngine
from backend.scenario_engine import PHASES, ScenarioEngine


def build_responder() -> LLMEngine:
    scenario = ScenarioEngine()
    scenario.scenario_data = {
        "name": "Monsoon flood exercise",
        "type": "Flood",
        "context": "River levels are rising after sustained rainfall.",
    }
    scenario.injects_data = {"injects": []}
    return LLMEngine(scenario)


def test_prompt_has_one_mandate_copy_and_natural_conversation_rules():
    responder = build_responder()
    wing_id = "operations_logistic"
    wing_name = responder.get_wing_name(wing_id)
    system_prompt = responder._build_system_prompt(wing_name, wing_id, PHASES[0]["id"])
    user_prompt = responder._build_user_prompt(
        wing_id,
        wing_name,
        PHASES[0],
        "We have checked our available stock.",
    )
    combined = f"{system_prompt}\n{user_prompt}"

    assert combined.count("Mandate scope:") == 1
    assert "Ask no more than one focused question per turn" in system_prompt
    assert "Do not force every turn into a mandate checklist" in system_prompt
    assert "Do not invent operational details" in system_prompt
    assert "Phase-relevant responsibilities:" not in system_prompt
    assert "Do not quiz the participant for names of tools" in system_prompt
    assert "Question selection rule" in system_prompt
    assert 'Do not ask for something "specific"' in system_prompt


def test_greeting_prompt_orients_instead_of_appraising():
    responder = build_responder()
    wing_id = "operations_logistic"
    greeting_prompt = responder._build_user_prompt(
        wing_id,
        responder.get_wing_name(wing_id),
        PHASES[0],
        "hello",
    )

    assert "Appraise their response" not in greeting_prompt
    assert "Open with a concise situation orientation" in greeting_prompt


def test_narrow_draft_gets_one_command_level_rewrite():
    responder = build_responder()

    class SequencedLLM:
        def __init__(self):
            self.calls = []

        def invoke(self, messages):
            self.calls.append(messages)

            class Result:
                content = (
                    "Which specific satellite-derived indices will you use?"
                    if len(self.calls) == 1
                    else "What preparedness decision should this analysis enable?"
                )

            return Result()

    llm = SequencedLLM()
    responder.llm = llm
    responder.rewrite_llm = llm

    response = responder.get_response(
        "operations_logistic",
        "d_minus_90",
        "We will review the exposed districts.",
    )

    assert response == "What preparedness decision should this analysis enable?"
    assert len(llm.calls) == 2
    assert "Rewrite the moderator draft" in llm.calls[1][-1].content


def test_participant_or_inject_introduced_technical_terms_are_preserved():
    responder = build_responder()

    class SingleDraftLLM:
        calls = 0

        def __init__(self, content):
            self.content = content

        def invoke(self, _messages):
            self.calls += 1

            class Result:
                content = self.content

            return Result()

    participant_llm = SingleDraftLLM("Which models will inform that decision?")
    responder.llm = participant_llm
    response = responder.get_response(
        "operations_logistic",
        "d_minus_90",
        "We will compare the available models before deciding.",
    )
    assert response == "Which models will inform that decision?"
    assert participant_llm.calls == 1

    responder.scenario.injects_data = {
        "injects": [
            {
                "id": "satellite-required",
                "phase_id": "d_minus_90",
                "title": "Satellite review",
                "description": "Satellite imagery must support the current exposure assessment.",
                "severity": "HIGH",
                "required_wings": ["operations_logistic"],
            }
        ]
    }
    inject_llm = SingleDraftLLM("How will satellite imagery change your decision?")
    responder.llm = inject_llm
    response = responder.get_response(
        "operations_logistic",
        "d_minus_90",
        "We will update the exposure assessment.",
    )
    assert response == "How will satellite imagery change your decision?"
    assert inject_llm.calls == 1


def test_invalid_or_failed_rewrite_uses_safe_fallback():
    responder = build_responder()

    class StaticLLM:
        def __init__(self, content=None, error=None):
            self.content = content
            self.error = error

        def invoke(self, _messages):
            if self.error:
                raise self.error

            class Result:
                content = self.content

            return Result()

    responder.llm = StaticLLM(
        "Use GIS sensors immediately. Which specific dashboard will you configure?"
    )
    responder.rewrite_llm = StaticLLM(
        "Which specific API workflow and threshold will you configure?"
    )
    response = responder.get_response(
        "operations_logistic",
        "d_minus_90",
        "We will coordinate with the departments.",
    )
    assert response == "What preparedness outcome should that coordination achieve?"

    responder.rewrite_llm = StaticLLM(error=TimeoutError("rewrite timed out"))
    response = responder.get_response(
        "operations_logistic",
        "d_minus_90",
        "We will coordinate with the departments.",
    )
    assert response == "What preparedness outcome should that coordination achieve?"


def test_greeting_with_polite_suffix_still_uses_orientation_mode():
    responder = build_responder()
    assert responder._is_greeting("Hello, good morning")
    assert not responder._is_greeting("Hi, the bridge has collapsed")


def test_history_terms_and_non_stock_acknowledgement_do_not_trigger_rewrite():
    responder = build_responder()

    class CountingLLM:
        def __init__(self, content):
            self.content = content
            self.calls = 0

        def invoke(self, _messages):
            self.calls += 1

            class Result:
                content = self.content

            return Result()

    history_llm = CountingLLM("How will those models affect the decision?")
    responder.llm = history_llm
    response = responder.get_response(
        "operations_logistic",
        "d_minus_90",
        "We will use them in our assessment.",
        history=[
            {
                "role": "user",
                "content": "We will compare the available models.",
                "phase_id": "d_minus_90",
            },
            {"role": "assistant", "content": "That comparison can clarify the risk."},
        ],
    )
    assert response == "How will those models affect the decision?"
    assert history_llm.calls == 1

    acknowledgement_llm = CountingLLM(
        "You acknowledged the evacuation constraint. What outcome should follow?"
    )
    responder.llm = acknowledgement_llm
    response = responder.get_response(
        "operations_logistic",
        "d_minus_90",
        "We accounted for the evacuation constraint.",
    )
    assert response.startswith("You acknowledged the evacuation constraint.")
    assert acknowledgement_llm.calls == 1


def test_safe_fallback_varies_against_conversation_history():
    responder = build_responder()
    draft = "Use LiDAR tools now. Which specific dashboard should you configure?"
    first = responder._safe_response_fallback(
        draft,
        "We will coordinate with departments.",
        "",
    )
    second = responder._safe_response_fallback(
        draft,
        "We will coordinate with departments.",
        "",
        history=[{"role": "assistant", "content": first}],
    )

    assert first != second
    assert "LiDAR" not in first + second
    assert "dashboard" not in (first + second).lower()

    all_variants = [
        {"role": "assistant", "content": "What preparedness outcome should that coordination achieve?"},
        {"role": "assistant", "content": "Which decision should that coordination unlock?"},
        {"role": "assistant", "content": "Who is accountable for turning that coordination into action?"},
    ]
    exhausted = responder._safe_response_fallback(
        draft,
        "We will coordinate with departments.",
        "",
        history=all_variants,
    )
    assert not exhausted.endswith(all_variants[-1]["content"])


def test_prior_assistant_hallucination_is_not_trusted_as_grounding():
    responder = build_responder()

    class StaticLLM:
        def __init__(self, content):
            self.content = content
            self.calls = 0

        def invoke(self, _messages):
            self.calls += 1

            class Result:
                content = self.content

            return Result()

    draft_llm = StaticLLM("How will LiDAR affect that decision?")
    rewrite_llm = StaticLLM("What preparedness decision should follow?")
    responder.llm = draft_llm
    responder.rewrite_llm = rewrite_llm

    response = responder.get_response(
        "operations_logistic",
        "d_minus_90",
        "We will proceed with the assessment.",
        history=[
            {"role": "assistant", "content": "Use LiDAR to map the area."},
            {"role": "user", "content": "The legacy note also mentioned LiDAR."},
        ],
    )

    assert response == "What preparedness decision should follow?"
    assert draft_llm.calls == 1
    assert rewrite_llm.calls == 1
