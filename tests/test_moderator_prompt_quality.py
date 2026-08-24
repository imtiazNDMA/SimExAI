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


def test_quality_rewrite_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("LMSTUDIO_REWRITE_ENABLED", raising=False)
    responder = build_responder()
    assert responder.rewrite_llm is None


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


def test_prompt_includes_phase_responsibilities_and_other_wing_ownership():
    responder = build_responder()
    system_prompt = responder._build_system_prompt(
        responder.get_wing_name("technical_early_warning"),
        "technical_early_warning",
        "d_day",
    )

    assert "Current-phase responsibilities:" in system_prompt
    assert "Provide early warning updates and risk intelligence" in system_prompt
    assert "Current-phase exercise actions:" in system_prompt
    assert "Validate the hazard trigger" in system_prompt
    assert "Other-wing ownership boundaries:" in system_prompt
    assert "Regional & Military Collaboration and Media Wing" in system_prompt
    assert "Operations and Logistic Wing" in system_prompt
    assert "An inject does not transfer another wing's responsibilities" in system_prompt


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


def test_semantically_repeated_follow_up_changes_lens():
    responder = build_responder()

    class StaticLLM:
        def invoke(self, _messages):
            class Result:
                content = (
                    "Detecting anomalies is a useful first step. "
                    "What decision must that approach support?"
                )

            return Result()

    responder.llm = StaticLLM()
    response = responder.get_response(
        "technical_early_warning",
        "d_minus_90",
        "Once the data is ingested, we analyse it and detect anomalies.",
        history=[
            {
                "role": "assistant",
                "content": "What operational outcome should follow from that approach?",
                "phase_id": "d_minus_90",
            }
        ],
    )

    assert "What decision must that approach support?" not in response
    assert response.endswith("What consequence would make you adjust that approach?")


def test_technical_early_warning_rejects_media_and_operations_ownership():
    responder = build_responder()

    class StaticLLM:
        def __init__(self, content):
            self.content = content

        def invoke(self, _messages):
            class Result:
                content = self.content

            return Result()

    for draft in (
        "Which media briefing and public messaging strategy will your wing lead?",
        "How will your wing deploy relief trucks and manage relief distribution?",
    ):
        responder.llm = StaticLLM(draft)
        response = responder.get_response(
            "technical_early_warning",
            "d_minus_90",
            "We are monitoring the hazard and updating our risk analysis.",
        )

        assert response != draft
        assert "media briefing" not in response.lower()
        assert "relief" not in response.lower()


def test_technical_early_warning_allows_boundary_aware_handoff():
    responder = build_responder()

    class StaticLLM:
        def invoke(self, _messages):
            class Result:
                content = (
                    "What verified warning content will you provide to RM & Media "
                    "for public dissemination?"
                )

            return Result()

    responder.llm = StaticLLM()
    response = responder.get_response(
        "technical_early_warning",
        "d_minus_90",
        "We will validate the warning before sharing it with response wings.",
    )

    assert response == (
        "What verified warning content will you provide to RM & Media "
        "for public dissemination?"
    )


def test_role_owners_keep_their_media_and_operations_questions():
    responder = build_responder()

    class StaticLLM:
        def __init__(self, content):
            self.content = content

        def invoke(self, _messages):
            class Result:
                content = self.content

            return Result()

    cases = (
        (
            "regional_military_media",
            "Which media briefing and public messaging strategy will your wing lead?",
        ),
        (
            "operations_logistic",
            "How will your wing deploy relief trucks and manage relief distribution?",
        ),
    )
    for wing_id, draft in cases:
        responder.llm = StaticLLM(draft)
        response = responder.get_response(
            wing_id,
            "d_minus_90",
            "We are reviewing our current responsibilities.",
        )
        assert response == draft


def test_technical_early_warning_rejects_distinct_other_wing_ownership():
    responder = build_responder()
    violations = (
        "How will your wing design volunteer training curricula?",
        "How will your wing maintain NDMA network hardware?",
        "How will your wing formulate national DRR policy?",
        "How will your wing conduct structural safety inspections?",
        "How will your wing activate response clusters and field deployments?",
        "Which public messaging strategy will your wing lead?",
        "How will your wing manage relief distribution?",
        "How will your wing obtain diplomatic clearances for foreign response teams?",
    )

    for draft in violations:
        assert responder._has_out_of_role_ownership(
            draft, "technical_early_warning"
        ), draft


def test_role_boundary_validation_is_clause_scoped():
    responder = build_responder()

    mixed = (
        "Provide verified warnings to RM & Media. "
        "How will your wing manage relief distribution?"
    )
    contextual = (
        "Relief distribution remains constrained. "
        "How will you coordinate the warning update with PDMAs?"
    )
    same_clause = (
        "What warning will you provide to Plans and how will your wing manage "
        "relief distribution?"
    )
    named_assignment = (
        "Technical Early Warning Wing will lead the media briefing."
    )
    valid_coordination = (
        "How will you coordinate diplomatic clearances with International Collaboration?"
    )
    direct_coordination = "How will your wing coordinate relief distribution?"
    abbreviated_assignment = "Tech EW will lead the media briefing."

    assert responder._has_out_of_role_ownership(mixed, "technical_early_warning")
    assert responder._has_out_of_role_ownership(
        same_clause, "technical_early_warning"
    )
    assert responder._has_out_of_role_ownership(
        named_assignment, "technical_early_warning"
    )
    assert responder._has_out_of_role_ownership(
        direct_coordination, "technical_early_warning"
    )
    assert responder._has_out_of_role_ownership(
        abbreviated_assignment, "technical_early_warning"
    )
    assert not responder._has_out_of_role_ownership(
        contextual, "technical_early_warning"
    )
    assert not responder._has_out_of_role_ownership(
        valid_coordination, "plans"
    )
    assert not responder._has_out_of_role_ownership(
        "How will your wing formulate national contingency plans?",
        "operations_logistic",
    )


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
