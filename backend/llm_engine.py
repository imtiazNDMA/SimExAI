"""LangChain/LM Studio-backed response engine for NDMA wing chat."""
import os
import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .scenario_engine import ScenarioEngine
from .template_engine import TemplateEngine


PROFANITY_PATTERNS = [
    r"\bf+u+c+k+\w*\b",
    r"\bs+h+i+t+\w*\b",
    r"\bb+i+t+c+h+\w*\b",
    r"\ba+s+s+h+o+l+e+\w*\b",
    r"\bb+a+s+t+a+r+d+\w*\b",
    r"\bd+a+m+n+\w*\b",
    r"\bc+u+n+t+\w*\b",
    r"\bm+o+t+h+e+r+f+u+c+k+\w*\b",
    r"\bd+i+c+k+\w*\b",
    r"\bp+u+s+s+y+\w*\b",
    r"\bw+a+n+k+e+r+\w*\b",
]

PROFANITY_RE = re.compile("|".join(PROFANITY_PATTERNS), re.IGNORECASE)
INJECT_CONTEXT_TOKEN_BUDGET = 1200
SEVERITY_RANK = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
RETRIEVAL_CANDIDATE_COUNT = 30
RETRIEVAL_CONTEXT_LIMIT = 5
STOCK_RESPONSE_RE = re.compile(
    r"(?:^\s*acknowledged\b|\bbased on your mandate\b|"
    r"\bwhat are your next steps\b|\bhow do you intend to\b)",
    re.IGNORECASE | re.MULTILINE,
)
TECHNICAL_CONCEPT_PATTERNS = {
    "algorithm": re.compile(r"\balgorithms?\b", re.IGNORECASE),
    "api": re.compile(r"\bapis?\b", re.IGNORECASE),
    "calibration": re.compile(r"\bcalibrat\w*\b", re.IGNORECASE),
    "dashboard": re.compile(r"\bdashboards?\b", re.IGNORECASE),
    "database": re.compile(r"\bdatabases?\b", re.IGNORECASE),
    "data stream": re.compile(r"\bdata streams?\b", re.IGNORECASE),
    "drone": re.compile(r"\bdrones?\b", re.IGNORECASE),
    "geospatial": re.compile(r"\bgeospatial\b", re.IGNORECASE),
    "gis": re.compile(r"\bgis\b", re.IGNORECASE),
    "index": re.compile(r"\b(?:index|indices)\b", re.IGNORECASE),
    "lidar": re.compile(r"\blidar\b", re.IGNORECASE),
    "model": re.compile(r"\bmodels?\b", re.IGNORECASE),
    "parameter": re.compile(r"\bparameters?\b", re.IGNORECASE),
    "platform": re.compile(r"\bplatforms?\b", re.IGNORECASE),
    "protocol": re.compile(r"\bprotocols?\b", re.IGNORECASE),
    "remote sensing": re.compile(r"\bremote sensing\b", re.IGNORECASE),
    "satellite": re.compile(r"\bsatellite\w*\b", re.IGNORECASE),
    "sensor": re.compile(r"\bsensors?\b", re.IGNORECASE),
    "software": re.compile(r"\bsoftware\b", re.IGNORECASE),
    "sop": re.compile(r"\bsops?\b", re.IGNORECASE),
    "technical product": re.compile(r"\btechnical products?\b", re.IGNORECASE),
    "threshold": re.compile(r"\bthresholds?\b", re.IGNORECASE),
    "tool": re.compile(r"\btools?\b", re.IGNORECASE),
    "workflow": re.compile(r"\bworkflows?\b", re.IGNORECASE),
}
QUESTION_LENS_PATTERNS = (
    (
        "ownership",
        re.compile(r"\b(?:who|accountab\w*|responsib\w*|owners?|owns?|ownership)\b", re.IGNORECASE),
    ),
    (
        "trade_off",
        re.compile(r"\b(?:trade[ -]?offs?|balance|sacrifice|compromise)\b", re.IGNORECASE),
    ),
    (
        "contingency",
        re.compile(
            r"\b(?:consequen\w*|contingenc\w*|adjust\w*|change|fail\w*|worsen\w*)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "operational_purpose",
        re.compile(
            r"\b(?:decisions?|outcomes?|enable\w*|support\w*|unlock\w*|achieve\w*|preparedness choice)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "priority",
        re.compile(r"\b(?:priorit\w*|most important|greatest risk|primary risk)\b", re.IGNORECASE),
    ),
)
ROLE_OWNERSHIP_PATTERNS = (
    (
        {"technical_early_warning", "regional_military_media", "tech_equipment_maintenance"},
        re.compile(
            r"\b(?:hazard forecasts?|impact-based warnings?|early warning systems?|"
            r"hazard or exposure maps?|forecast thresholds?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        {"nidm"},
        re.compile(
            r"\b(?:volunteer training|training curricula|academic research|disaster archives?|"
            r"lessons learned programme)\b",
            re.IGNORECASE,
        ),
    ),
    (
        {"tech_equipment_maintenance"},
        re.compile(
            r"\b(?:network hardware|hardware maintenance|sitrep portals?|data backups?|"
            r"ict infrastructure)\b",
            re.IGNORECASE,
        ),
    ),
    (
        {"drr"},
        re.compile(
            r"\b(?:national drr polic(?:y|ies)|risk reduction frameworks?|sendai framework|"
            r"drr programmes?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        {"infrastructure_advisory_project_development"},
        re.compile(
            r"\b(?:structural safety inspections?|infrastructure repairs?|engineering works?|"
            r"infrastructure cost estimates?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        {"plans"},
        re.compile(
            r"\b(?:response clusters?|cluster activation|field deployments?|neoc activation)\b",
            re.IGNORECASE,
        ),
    ),
    (
        {"plans", "operations_logistic"},
        re.compile(r"\bnational contingency plans?\b", re.IGNORECASE),
    ),
    (
        {"regional_military_media"},
        re.compile(
            r"\b(?:media brief(?:ing)?s?|press releases?|public messaging|media strateg(?:y|ies)|"
            r"misinformation|spokespersons?|journalists?|public communication campaigns?|media line)\b",
            re.IGNORECASE,
        ),
    ),
    (
        {"operations_logistic"},
        re.compile(
            r"\b(?:relief trucks?|relief distribution|rescue operations?|evacuation operations?|"
            r"relief camps?|warehouses?|procurement|search and rescue)\b",
            re.IGNORECASE,
        ),
    ),
    (
        {"international_collaboration"},
        re.compile(
            r"\b(?:international assistance requests?|diplomatic clearances?|foreign response "
            r"teams?|donor pledges?|international donors?)\b",
            re.IGNORECASE,
        ),
    ),
)
ROLE_OWNERSHIP_CUE_RE = re.compile(
    r"\b(?:your wing|you)\b.*\b(?:lead|manage|deploy|draft|issue|publish|run|develop|"
    r"formulate|coordinate|execute|operate|activate|own|handle|oversee|design|maintain|"
    r"conduct|obtain)\w*\b|"
    r"\b(?:lead|manage|deploy|draft|issue|publish|run|develop|formulate|coordinate|"
    r"execute|operate|activate|coordinate|own|handle|oversee|design|maintain|conduct|obtain)\w*\b.*"
    r"\b(?:your wing|you)\b|"
    r"\b(?:your wing|you)\b.*\b(?:accountable|responsible)\b",
    re.IGNORECASE,
)
BOUNDARY_HANDOFF_RE = re.compile(
    r"\b(?:(?:provide|share|send|hand(?:off)?|brief)\w*\b.*?\bto|"
    r"coordinate\w*\b.*?\bwith)\s+(?:the\s+)?"
    r"(?:tech(?:nical)?\s+early\s+warning(?:\s+wing)?|tech(?:nical)?\s+e\s*&\s*m|"
    r"nidm|drr(?:\s+wing)?|ia\s*&\s*pd|rm\s*&\s*media|media wing|"
    r"operations(?:\s+and\s+logistic)?(?:\s+wing)?|plans(?:\s+wing)?|"
    r"international collaboration(?:\s+wing)?|response wings?|other wings?)\b",
    re.IGNORECASE,
)


class LLMEngine:
    """Generate wing responses with LangChain against an OpenAI-compatible server.

    Targets LM Studio by default. TemplateEngine is intentionally used only for
    stable exercise metadata: wing names, icons, and phase action lists. Chat
    responses are generated by the model and are not pulled from wing response
    templates.

    Note on token budgets: the default model is a reasoning model that spends
    a large, variable number of tokens on internal reasoning before emitting
    any answer (measured: ~100-1700 tokens). max_tokens covers reasoning plus
    the visible answer, so the budgets below are deliberately generous — a
    tight budget yields an empty response, not a short one.
    """

    def __init__(
        self,
        scenario: ScenarioEngine,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: int | None = None,
    ):
        self.scenario = scenario
        self.vector_store = None
        self.metadata = TemplateEngine()
        self.base_url = self._normalize_base_url(
            base_url or os.getenv("LMSTUDIO_BASE_URL") or "http://localhost:1234/v1"
        )
        self.model = model or os.getenv("LMSTUDIO_MODEL") or "google/gemma-4-26b-a4b"
        self.api_key = os.getenv("LMSTUDIO_API_KEY", "lm-studio")  # LM Studio ignores the value
        self.timeout_seconds = timeout_seconds or int(os.getenv("LMSTUDIO_TIMEOUT_SECONDS", "180"))
        self.upload_timeout_seconds = int(os.getenv("LMSTUDIO_UPLOAD_TIMEOUT_SECONDS", "600"))
        self.rewrite_enabled = os.getenv(
            "LMSTUDIO_REWRITE_ENABLED", "false"
        ).strip().lower() in {"1", "true", "yes", "on"}
        self.rewrite_timeout_seconds = int(os.getenv("LMSTUDIO_REWRITE_TIMEOUT_SECONDS", "60"))
        self.temperature = float(os.getenv("LMSTUDIO_TEMPERATURE", "0.45"))
        self.top_p = float(os.getenv("LMSTUDIO_TOP_P", "0.9"))
        self.max_tokens = int(os.getenv("LMSTUDIO_MAX_TOKENS", "3000"))
        # Extraction is a structured-output task: deterministic, and large enough
        # to hold every inject in a long scenario document.
        self.upload_temperature = float(os.getenv("LMSTUDIO_UPLOAD_TEMPERATURE", "0"))
        self.upload_max_tokens = int(os.getenv("LMSTUDIO_UPLOAD_MAX_TOKENS", "16000"))
        self.rewrite_max_tokens = int(os.getenv("LMSTUDIO_REWRITE_MAX_TOKENS", "2500"))
        self.llm = self._build_llm(self.timeout_seconds)
        self.rewrite_llm = (
            self._build_llm(
                self.rewrite_timeout_seconds,
                temperature=0.2,
                max_tokens=self.rewrite_max_tokens,
                max_retries=0,
            )
            if self.rewrite_enabled
            else None
        )
        self.upload_llm = self._build_llm(
            self.upload_timeout_seconds,
            temperature=self.upload_temperature,
            max_tokens=self.upload_max_tokens,
        )

    def _build_llm(
        self,
        timeout_seconds: int,
        temperature: float | None = None,
        max_tokens: int | None = None,
        max_retries: int = 1,
    ) -> ChatOpenAI:
        return ChatOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            model=self.model,
            streaming=False,
            temperature=self.temperature if temperature is None else temperature,
            top_p=self.top_p,
            max_tokens=self.max_tokens if max_tokens is None else max_tokens,
            timeout=timeout_seconds,
            max_retries=max_retries,
        )

    def _normalize_base_url(self, value: str) -> str:
        """Coerce a user-supplied URL to an OpenAI-compatible root ending in /v1."""
        base_url = str(value or "").strip().rstrip("/")
        for suffix in ("/chat/completions", "/completions"):
            if base_url.endswith(suffix):
                base_url = base_url[: -len(suffix)].rstrip("/")
        if not base_url.endswith("/v1"):
            base_url = f"{base_url}/v1"
        return base_url

    def set_vector_store(self, vector_store):
        self.vector_store = vector_store

    def format_llm_error(self, exc: Exception) -> str:
        detail = str(exc)
        lowered = detail.lower()
        hint = ""

        if "connection" in lowered or "connect" in lowered or "refused" in lowered:
            hint = (
                f" The LM Studio server does not appear to be running at {self.base_url}. "
                "Start LM Studio, open its Developer/Local Server tab, and start the server."
            )
        elif "model_not_found" in lowered or "404" in detail:
            hint = (
                f" The server is reachable but does not recognise the model '{self.model}'. "
                "Load that model in LM Studio, or set LMSTUDIO_MODEL to a model id listed by "
                f"{self.base_url}/models."
            )
        elif "timeout" in lowered or "timed out" in lowered:
            hint = (
                f" The request exceeded {self.timeout_seconds}s. This model reasons before "
                "answering, which is slow on large prompts — raise LMSTUDIO_TIMEOUT_SECONDS "
                "or use a smaller model."
            )

        return f"LM Studio model {self.model} at {self.base_url} failed: {detail}.{hint}".strip()

    def get_wings(self) -> list[dict]:
        return self.metadata.get_wings()

    def get_wing_name(self, wing_id: str) -> str:
        return self.metadata.get_wing_name(wing_id)

    def get_wing_icon(self, wing_id: str) -> str:
        return self.metadata.get_wing_icon(wing_id)

    def get_wing_actions(self, wing_id: str, phase_id: str) -> list[str]:
        return self.metadata.get_wing_actions(wing_id, phase_id)

    def get_wing_mandate(self, wing_id: str, phase_id: str) -> str:
        return self.metadata.get_wing_mandate(wing_id, phase_id)

    def normalize_wing_id(self, wing_id: str | None) -> str | None:
        return self.metadata.normalize_wing_id(wing_id)

    def get_response(
        self,
        wing_id: str,
        phase_id: str,
        user_message: str,
        history: list[dict] | None = None,
        inject_ledger: str | None = None,
        turn_mode: str | None = None,
    ) -> str:
        wing_id = self.normalize_wing_id(wing_id) or wing_id
        wing_name = self.get_wing_name(wing_id)
        if wing_name == wing_id:
            return f"Unknown wing: {wing_id}"

        if self._contains_profanity(user_message):
            return (
                "I can help with the simulation, but keep the language professional. "
                f"Send your operational question for {wing_name} and I will respond in role."
            )

        phase = self._get_phase(phase_id)
        is_phase_change = self._is_phase_change_prompt(user_message)
        if turn_mode not in {"orientation", "phase_briefing", "discussion"}:
            turn_mode = (
                "phase_briefing"
                if is_phase_change
                else "orientation"
                if self._is_greeting(user_message) and not history
                else "discussion"
            )
        is_phase_change = turn_mode == "phase_briefing" or is_phase_change
        
        retrieved_chunks = []
        if self.vector_store:
            scenario_id = getattr(self.scenario, 'scenario_id', None)
            if scenario_id:
                inject_count = len(self.scenario.injects_data.get("injects", []))
                retrieved_chunks = self.vector_store.retrieve(
                    query=user_message,
                    scenario_id=scenario_id,
                    top_k=max(
                        RETRIEVAL_CANDIDATE_COUNT,
                        inject_count + RETRIEVAL_CONTEXT_LIMIT,
                    ),
                )
                retrieved_chunks = self._filter_retrieved_chunks_for_wing(
                    retrieved_chunks, wing_id, phase_id
                )

        grounding_text = self._build_grounding_text(
            wing_id, phase, user_message, retrieved_chunks, history
        )

        messages = [
            SystemMessage(content=self._build_system_prompt(wing_name, wing_id, phase_id)),
            *self._build_history_messages(history),
            HumanMessage(content=self._build_user_prompt(
                wing_id,
                wing_name,
                phase,
                user_message,
                is_phase_change,
                retrieved_chunks,
                inject_ledger,
                turn_mode,
            )),
        ]

        try:
            result = self.llm.invoke(messages)
        except Exception as exc:
            return (
                f"{wing_name} AI is currently unable to reach the language model "
                f"({self.model}) at {self.base_url}. Backend detail: {self.format_llm_error(exc)}"
            )

        content = self._extract_content(result)
        content = self._strip_thinking(content)
        content = self._sanitize_output(content, suppress_welcome=is_phase_change)
        if content and self._needs_conversational_revision(
            content, user_message, grounding_text, history, wing_id
        ):
            content = self._revise_response(
                messages,
                content,
                user_message,
                grounding_text,
                history,
                wing_id,
                suppress_welcome=is_phase_change,
            )
        return content or "I could not generate a useful response. Please try again with a clearer exercise question."

    def _get_phase(self, phase_id: str) -> dict:
        for phase in self.scenario.get_all_phases():
            if phase["id"] == phase_id:
                return phase
        return self.scenario.get_current_phase()

    def _build_grounding_text(
        self,
        wing_id: str,
        phase: dict,
        user_message: str,
        retrieved_chunks: list[dict],
        history: list[dict] | None = None,
    ) -> str:
        scenario_data = (
            getattr(self.scenario, "scenario_data", None)
            or self.scenario.get_scenario_info()
        )
        injects = self.scenario.get_injects_for_phase(phase["id"], wing_id)
        parts = [self._format_scenario_context(scenario_data), user_message]
        parts.extend(
            f"{inject.get('title', '')} {inject.get('description', '')}"
            for inject in injects
        )
        parts.extend(str(chunk.get("text", "")) for chunk in retrieved_chunks)
        parts.extend(
            str(turn.get("content", ""))
            for turn in (history or [])[-12:]
            if turn.get("role") == "user"
            and turn.get("phase_id") == phase["id"]
        )
        return "\n".join(parts)

    def _build_history_messages(self, history: list[dict] | None) -> list:
        """Convert persisted turns to LLM messages with a bounded context window.

        Older turns beyond the window are condensed into a single system block so
        a long exercise never overflows the model context. The condensation is
        deterministic (no extra LLM call); a real summarizer can replace it later.
        """
        if not history:
            return []

        max_turns = 12
        messages = []
        if len(history) > max_turns:
            older = history[:-max_turns]
            condensed = "\n".join(
                f"- {turn.get('role', 'unknown')}: {str(turn.get('content', ''))[:200]}"
                for turn in older
            )
            messages.append(
                SystemMessage(content=f"Earlier conversation summary (condensed):\n{condensed}")
            )
            history = history[-max_turns:]

        for turn in history:
            content = str(turn.get("content", ""))
            role = turn.get("role")
            if role == "assistant":
                messages.append(AIMessage(content=content))
            elif role == "system":
                messages.append(SystemMessage(content=content))
            else:
                messages.append(HumanMessage(content=content))
        return messages

    def _filter_retrieved_chunks_for_wing(
        self, chunks: list[dict], wing_id: str, phase_id: str
    ) -> list[dict]:
        """Remove retrieved inject records for another wing or exercise phase."""
        injects_by_id = {
            str(inject.get("id")): inject
            for inject in self.scenario.injects_data.get("injects", [])
            if inject.get("id")
        }
        filtered = []
        for chunk in chunks:
            inject = injects_by_id.get(str(chunk.get("id")))
            if inject:
                target_wings = (
                    inject.get("required_wings") or inject.get("target_wings") or []
                )
                if inject.get("phase_id") != phase_id:
                    continue
                if target_wings and wing_id not in target_wings:
                    continue
            filtered.append(chunk)
        return filtered

    def _build_system_prompt(self, wing_name: str, wing_id: str, phase_id: str) -> str:
        mandate = self.get_wing_mandate(wing_id, phase_id)
        return f"""You are SimexAI, a senior exercise moderator for an NDMA Pakistan disaster simulation.
The participant represents {wing_name}.

Wing role boundary (use it to judge role relevance, not as a checklist or a source of scenario facts):
{mandate}

Moderation policy:
- Ground every situation statement in the supplied scenario, current phase, active injects, retrieved source context, or conversation history. Do not invent operational details, thresholds, assets, locations, damage, or events.
- Scenario evidence outranks generic mandate material. Do not force every turn into a mandate checklist or ask about a specialist process unless the scenario or participant raises it.
- Keep every appraisal and question inside the selected wing's responsibilities above. An inject does not transfer another wing's responsibilities. Mention another wing only to test the selected wing's mandated input, decision-support product, coordination commitment, or handoff; never ask the participant to own that other wing's downstream execution.
- Respond to the substance of the participant's last message before asking anything else. Recognize sound reasoning briefly; identify at most one important gap at a time.
- Ask no more than one focused question per turn. A question is optional when a clear statement or transition is more natural.
- Prefer decision-level questions about priorities, trade-offs, ownership, coordination outcomes, and consequences. Do not quiz the participant for names of tools, indices, parameters, platforms, data streams, models, or exact thresholds unless they introduced that technical subject or the active inject explicitly requires it.
- Question selection rule: on an opening turn, choose a broad scenario-relevant lens such as priority, risk judgement, or preparedness objective. On later turns, choose one useful lens only: the decision enabled, a trade-off, accountable ownership, the expected operational outcome, or a contingency. Change the substantive lens, not merely the wording, after each question. If the participant does not answer a follow-up directly, do not ask it again or paraphrase it; briefly identify the remaining gap, then use a different lens or provide the natural consequence or transition without a question. Do not ask for something "specific" or request a technical mechanism unless the participant asks for a technical deep dive or the current inject explicitly requires that mechanism.
- Do not solve the exercise, prescribe a complete action plan, or reveal future injects. Test judgement through realistic consequences and selective follow-up.
- Use conversation history to avoid repeating welcomes, facts, feedback, and question patterns.

Voice and style:
- Sound like an experienced Pakistani disaster-management exercise director: calm, precise, credible, and collaborative.
- Default to 2-4 natural sentences in short paragraphs. Use bullets only when the participant asks for a list or the information genuinely requires one.
- Avoid stock openings and closings such as "acknowledged", "based on your mandate", "what are your next steps", and "how do you intend to".
- Do not mention prompts, templates, retrieval, LangChain, LM Studio, or that you are an AI."""

    def _build_user_prompt(
        self,
        wing_id: str,
        wing_name: str,
        phase: dict,
        user_message: str,
        is_phase_change: bool = False,
        retrieved_chunks: list = None,
        inject_ledger: str = None,
        turn_mode: str | None = None,
    ) -> str:
        scenario_data = getattr(self.scenario, "scenario_data", None) or self.scenario.get_scenario_info()
        injects = self.scenario.get_injects_for_phase(phase["id"], wing_id)
        scenario_summary = self._format_scenario_context(scenario_data)
        phase_summary = self._format_mapping(phase, skip_keys={"is_active", "is_completed"})

        inject_text = self._format_inject_context(injects, retrieved_chunks)
        ledger_text = f"""
Inject status ledger (delivered = already presented to the participant; addressed = the participant has already handled it):
{inject_ledger}
""" if inject_ledger else ""
        turn_mode = turn_mode or (
            "phase_briefing"
            if is_phase_change
            else "orientation"
            if self._is_greeting(user_message)
            else "discussion"
        )
        turn_instructions = {
            "orientation": (
                "Open with a concise situation orientation grounded in the scenario and the "
                "highest-priority current inject. Ask one broad command-level opening question "
                "suited to this scenario; vary between priority, risk judgement, and preparedness "
                "objective rather than using a fixed formula. Keep it answerable without naming a "
                "technical method unless the inject requires one. Do not appraise, quiz them on a "
                "niche mandate function, or list recommended actions."
            ),
            "phase_briefing": (
                "Orient the participant to the authoritative current phase without another welcome "
                "or role acknowledgement. Do not infer whether the timeline moved forward, returned, "
                "or reset. Frame every consequence through this wing's current-phase "
                "responsibilities and active injects. End with one decision question owned by this "
                "wing; do not transfer media, field operations, logistics, or another wing's work "
                "to the participant, and do not list a complete response plan."
            ),
            "discussion": (
                "Respond directly to the participant's substance. Briefly note one sound element "
                "or one consequential gap using scenario evidence. Ask one follow-up only if it "
                "advances a decision, trade-off, ownership commitment, or scenario consequence; "
                "select a different substantive lens from the previous moderator question. Never "
                "repeat or paraphrase an unanswered question about the decision or operational "
                "outcome; state the gap and move to another lens or a natural transition. Do not "
                "turn a broad operational answer into a technical-detail quiz or ask which tools, "
                "data, indices, parameters, models, platforms, workflows, or technical products "
                "they will use unless that detail is explicit in the current inject. For coordination "
                "answers, test the preparedness decision or outcome that coordination must enable. "
                "Otherwise provide the natural consequence or transition."
            ),
        }[turn_mode]

        rag_section = ""
        if retrieved_chunks:
            rag_text = "\n".join(
                f"- [{c['score']:.2f}] {c['text']}"
                for c in retrieved_chunks[:RETRIEVAL_CONTEXT_LIMIT]
            )
            rag_section = f"""
Retrieved context from scenario documents (use as primary reference):
{rag_text}
"""

        return f"""Authoritative scenario evidence:
{scenario_summary}
{rag_section}
Current phase timeline:
{phase_summary}

Participant's Wing: {wing_name}

Current injects relevant to this wing:
{inject_text}
{ledger_text}
Participant message:
{user_message}

Turn objective ({turn_mode}):
{turn_instructions}

Respond now in natural prose. Stay within the evidence above and do not introduce a different hazard."""

    def _format_inject_context(
        self,
        injects: list[dict],
        retrieved_chunks: list[dict] | None = None,
        token_budget: int = INJECT_CONTEXT_TOKEN_BUDGET,
    ) -> str:
        """Rank wing-relevant injects and fit them into an approximate token budget."""
        if not injects:
            return "- No active injects for this phase."

        retrieval_scores = {
            str(chunk.get("id")): float(chunk.get("score") or 0)
            for chunk in (retrieved_chunks or [])
            if chunk.get("id")
        }
        ranked = sorted(
            enumerate(injects),
            key=lambda pair: (
                SEVERITY_RANK.get(str(pair[1].get("severity", "")).upper(), 0),
                retrieval_scores.get(str(pair[1].get("id")), 0),
                -pair[0],
            ),
            reverse=True,
        )

        lines = []
        remaining_tokens = token_budget
        for _, item in ranked:
            line = (
                f"- {item.get('time_offset', 'TBD')}: {item.get('title', 'Untitled inject')} "
                f"({item.get('severity', 'MEDIUM')}) - {item.get('description', '')}"
            )
            estimated_tokens = max(1, (len(line) + 3) // 4)
            if estimated_tokens <= remaining_tokens:
                lines.append(line)
                remaining_tokens -= estimated_tokens
                continue
            if not lines and remaining_tokens > 1:
                max_chars = remaining_tokens * 4
                lines.append(f"{line[:max_chars - 3].rstrip()}...")
                break

        return "\n".join(lines) or "- No active injects fit the context budget."

    def _format_scenario_context(self, scenario_data: dict) -> str:
        lines = []
        preferred_keys = ["name", "type", "event_time", "context"]
        for key in preferred_keys:
            if scenario_data.get(key) not in (None, "", [], {}):
                lines.append(f"- {self._label(key)}: {scenario_data[key]}")

        for key, value in scenario_data.items():
            if key in {*preferred_keys, "id", "phases"} or value in (None, "", [], {}):
                continue
            if isinstance(value, dict):
                lines.append(f"- {self._label(key)}:")
                lines.extend(self._format_mapping(value, indent=2))
            elif isinstance(value, list):
                lines.append(f"- {self._label(key)}:")
                lines.extend(f"  - {item}" for item in value)
            else:
                lines.append(f"- {self._label(key)}: {value}")

        return "\n".join(lines) if lines else "- Scenario: Not specified"

    def _format_mapping(self, data: dict, indent: int = 0, skip_keys: set[str] | None = None) -> list[str] | str:
        skip_keys = skip_keys or set()
        prefix = " " * indent
        lines = []
        for key, value in data.items():
            if key in skip_keys or value in (None, "", [], {}):
                continue
            if isinstance(value, dict):
                lines.append(f"{prefix}- {self._label(key)}:")
                nested = self._format_mapping(value, indent=indent + 2, skip_keys=skip_keys)
                lines.extend(nested if isinstance(nested, list) else nested.splitlines())
            elif isinstance(value, list):
                lines.append(f"{prefix}- {self._label(key)}:")
                lines.extend(f"{prefix}  - {item}" for item in value)
            else:
                lines.append(f"{prefix}- {self._label(key)}: {value}")
        if indent:
            return lines
        return "\n".join(lines) if lines else "- Not specified"

    def _label(self, key: str) -> str:
        return key.replace("_", " ").strip().title()

    def _extract_content(self, result) -> str:
        content = getattr(result, "content", result)
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    parts.append(str(item.get("text") or item.get("content") or ""))
                else:
                    parts.append(str(item))
            return "\n".join(part for part in parts if part).strip()
        return str(content).strip()

    def _strip_thinking(self, content: str) -> str:
        if "</think>" in content:
            return content.split("</think>", 1)[1].strip()
        return content

    def _contains_profanity(self, text: str) -> bool:
        return bool(PROFANITY_RE.search(text or ""))

    def _is_phase_change_prompt(self, text: str) -> bool:
        normalized = (text or "").lower()
        return (
            "phase advancement notice" in normalized
            or "advanced to phase" in normalized
            or ("advanced to" in normalized and "phase" in normalized)
        )

    def _is_greeting(self, text: str) -> bool:
        normalized = re.sub(r"[^a-z]+", " ", (text or "").lower()).strip()
        greetings = {
            "hello",
            "hi",
            "hey",
            "greetings",
            "salam",
            "assalam o alaikum",
            "assalam u alaikum",
        }
        if normalized in greetings:
            return True
        courtesy_words = {
            "all", "afternoon", "everyone", "evening", "good", "morning", "team", "there"
        }
        for greeting in sorted(greetings, key=len, reverse=True):
            if normalized.startswith(f"{greeting} "):
                remainder = normalized[len(greeting):].strip().split()
                return bool(remainder) and set(remainder).issubset(courtesy_words)
        return False

    def _technical_concepts(self, text: str) -> set[str]:
        return {
            name
            for name, pattern in TECHNICAL_CONCEPT_PATTERNS.items()
            if pattern.search(text or "")
        }

    def _needs_conversational_revision(
        self,
        content: str,
        user_message: str,
        grounding_text: str,
        history: list[dict] | None = None,
        wing_id: str | None = None,
    ) -> bool:
        if content.count("?") > 1 or STOCK_RESPONSE_RE.search(content):
            return True
        if any(
            re.search(r"\bspecific\b", question, re.IGNORECASE)
            for question in re.findall(r"[^.!?]*\?", content)
        ) and not re.search(r"\bspecific\b", user_message or "", re.IGNORECASE):
            return True
        unsupported = self._technical_concepts(content) - self._technical_concepts(
            grounding_text
        )
        return (
            bool(unsupported)
            or self._repeats_latest_question_lens(content, history)
            or self._has_out_of_role_ownership(content, wing_id)
        )

    def _has_out_of_role_ownership(self, text: str, wing_id: str | None) -> bool:
        if not wing_id:
            return False
        clauses = re.split(r"(?<=[.!?;])\s+|\s+(?:but|however|then)\s+", text or "")
        for clause in clauses:
            candidate = BOUNDARY_HANDOFF_RE.sub("", clause)
            if not self._has_ownership_cue(candidate, wing_id):
                continue
            for owner_wings, topic_pattern in ROLE_OWNERSHIP_PATTERNS:
                if wing_id not in owner_wings and topic_pattern.search(candidate):
                    return True
        return False

    def _has_ownership_cue(self, clause: str, wing_id: str) -> bool:
        if ROLE_OWNERSHIP_CUE_RE.search(clause):
            return True
        wing = self.metadata.mandates.get_wing(wing_id) or {}
        wing_name = re.sub(r"\s*\([^)]*\)\s*$", "", self.get_wing_name(wing_id))
        references = {
            wing_name,
            wing_id.replace("_", " "),
            str(wing.get("short_name", "")),
            str(wing.get("abbreviation", "")),
        }
        verbs = (
            r"lead|manage|deploy|draft|issue|publish|run|develop|formulate|coordinate|execute|"
            r"operate|activate|own|handle|oversee|design|maintain|conduct|obtain"
        )
        return any(
            re.search(
                rf"(?:\b{re.escape(reference)}\b.*\b(?:{verbs})\w*\b|"
                rf"\b(?:{verbs})\w*\b.*\b{re.escape(reference)}\b)",
                clause,
                re.IGNORECASE,
            )
            for reference in references
            if reference
        )

    def _question_lens(self, text: str) -> str | None:
        question = next(iter(re.findall(r"[^.!?]*\?", text or "")), "")
        for lens, pattern in QUESTION_LENS_PATTERNS:
            if pattern.search(question):
                return lens
        return None

    def _repeats_latest_question_lens(
        self, content: str, history: list[dict] | None
    ) -> bool:
        current_lens = self._question_lens(content)
        if not current_lens:
            return False
        latest_assistant = next(
            (
                str(turn.get("content", ""))
                for turn in reversed(history or [])
                if turn.get("role") == "assistant" and "?" in str(turn.get("content", ""))
            ),
            "",
        )
        return self._question_lens(latest_assistant) == current_lens

    def _revise_response(
        self,
        messages: list,
        draft: str,
        user_message: str,
        grounding_text: str,
        history: list[dict] | None = None,
        wing_id: str | None = None,
        suppress_welcome: bool = False,
    ) -> str:
        supported_concepts = ", ".join(sorted(self._technical_concepts(grounding_text)))
        supported_concepts = supported_concepts or "none"
        if self.rewrite_llm is None:
            return self._safe_response_fallback(
                draft, user_message, grounding_text, history, wing_id
            )
        revision_request = HumanMessage(content=f"""Rewrite the moderator draft below before it is shown.

Participant message:
{user_message}

Draft:
{draft}

Technical concepts explicitly supported by the participant, scenario, retrieved evidence, or current inject:
{supported_concepts}

Keep valid scenario facts and concise feedback. Remove unsupported specialist mechanisms, tools, data sources, indices, parameters, models, platforms, thresholds, protocols, workflows, or technical products; preserve any concept listed as supported above when it is relevant. Remove any request for the participant to lead or execute another wing's responsibilities; coordination may ask only for this wing's mandated input or handoff. Replace the question with at most one natural command-level question about a priority, decision, trade-off, accountable owner, operational outcome, or contingency. Do not use the word "specific" unless the participant did. Use 2-4 natural sentences and output only the rewritten response.""")
        try:
            result = self.rewrite_llm.invoke([
                *messages,
                AIMessage(content=draft),
                revision_request,
            ])
        except Exception:
            return self._safe_response_fallback(
                draft, user_message, grounding_text, history, wing_id
            )
        revised = self._extract_content(result)
        revised = self._strip_thinking(revised)
        revised = self._sanitize_output(revised, suppress_welcome=suppress_welcome)
        if revised and not self._needs_conversational_revision(
            revised, user_message, grounding_text, history, wing_id
        ):
            return revised
        return self._safe_response_fallback(
            draft, user_message, grounding_text, history, wing_id
        )

    def _safe_response_fallback(
        self,
        draft: str,
        user_message: str,
        grounding_text: str,
        history: list[dict] | None = None,
        wing_id: str | None = None,
    ) -> str:
        supported = self._technical_concepts(grounding_text)
        safe_statements = []
        for sentence in re.split(r"(?<=[.!?])\s+", draft or ""):
            if "?" in sentence or STOCK_RESPONSE_RE.search(sentence):
                continue
            if self._has_out_of_role_ownership(sentence, wing_id):
                continue
            if self._technical_concepts(sentence) - supported:
                continue
            if sentence.strip():
                safe_statements.append(sentence.strip())
            if len(safe_statements) == 2:
                break

        lowered = (user_message or "").lower()
        if any(word in lowered for word in ("coordinate", "coordination", "department")):
            questions = [
                "What preparedness outcome should that coordination achieve?",
                "Which decision should that coordination unlock?",
                "Who is accountable for turning that coordination into action?",
            ]
        elif any(word in lowered for word in ("assess", "review", "verify", "identify", "map")):
            questions = [
                "What decision should that assessment enable?",
                "Which preparedness choice depends on that assessment?",
                "What should change once that assessment is complete?",
            ]
        elif "priority" in lowered:
            questions = [
                "What trade-off could affect that priority?",
                "Who owns the decision behind that priority?",
                "What outcome will show that priority was correct?",
            ]
        else:
            questions = [
                "What operational outcome should follow from that approach?",
                "What decision must that approach support?",
                "What consequence would make you adjust that approach?",
            ]
        prior_text = " ".join(
            str(turn.get("content", "")) for turn in (history or [])
        ).lower()
        latest_assistant = next(
            (
                str(turn.get("content", ""))
                for turn in reversed(history or [])
                if turn.get("role") == "assistant"
            ),
            "",
        )
        previous_lens = self._question_lens(latest_assistant)
        available = [
            candidate
            for candidate in questions
            if candidate.lower() not in prior_text
            and self._question_lens(candidate) != previous_lens
        ]
        if available:
            question = available[0]
        else:
            latest_assistant = latest_assistant.lower()
            alternatives = [
                candidate
                for candidate in questions
                if candidate.lower() not in latest_assistant
            ]
            question = (alternatives or questions)[
                len(history or []) % len(alternatives or questions)
            ]
        return " ".join([*safe_statements, question])

    def _sanitize_output(self, text: str, suppress_welcome: bool = False) -> str:
        cleaned = PROFANITY_RE.sub("[filtered]", text or "").strip()
        if suppress_welcome:
            cleaned = self._strip_repeated_welcome(cleaned)
        return cleaned.strip()

    def _strip_repeated_welcome(self, text: str) -> str:
        cleaned = text or ""
        repeated_patterns = [
            r"^\s*welcome\s+to\s+.*?(?:\.|\n)\s*",
            r"^\s*i\s+acknowledge\s+your\s+presence\s+as\s+.*?(?:\.|\n)\s*",
            r"^\s*i\s+acknowledge\s+your\s+role\s+as\s+.*?(?:\.|\n)\s*",
        ]

        previous = None
        while previous != cleaned:
            previous = cleaned
            for pattern in repeated_patterns:
                cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE | re.DOTALL)

        return cleaned.lstrip(" \n:-")
