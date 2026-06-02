"""Template response engine.

Wing metadata and action lists come from data/Mandate/mandate.json. The
template file remains as the keyword-response fallback for non-LLM runs.
"""
import json
from pathlib import Path

from .mandate import MandateRegistry


DATA_DIR = Path(__file__).parent.parent / "data"


class TemplateEngine:
    """Returns template-based responses for wing + phase + keyword combinations."""

    def __init__(self):
        self.mandates = MandateRegistry()
        self.templates = self._load_templates()

    def _load_templates(self) -> dict:
        path = DATA_DIR / "templates" / "wing_responses.json"
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_wings(self) -> list[dict]:
        """Return canonical wings with id, name, icon, and abbreviation."""
        return self.mandates.get_wings()

    def get_wing_name(self, wing_id: str) -> str:
        return self.mandates.get_wing_name(wing_id)

    def get_wing_icon(self, wing_id: str) -> str:
        return self.mandates.get_wing_icon(wing_id)

    def normalize_wing_id(self, wing_id: str | None) -> str | None:
        return self.mandates.normalize_wing_id(wing_id)

    def get_wing_actions(self, wing_id: str, phase_id: str) -> list[str]:
        """Get mandate-based action items for a wing in a specific phase."""
        actions = self.mandates.get_wing_actions(wing_id, phase_id)
        if actions:
            return actions

        canonical_id = self.normalize_wing_id(wing_id) or wing_id
        wing = self.templates.get("wings", {}).get(canonical_id, {})
        phase_data = wing.get("phases", {}).get(phase_id, {})
        return phase_data.get("actions", [])

    def get_wing_mandate(self, wing_id: str, phase_id: str) -> str:
        return self.mandates.format_mandate_for_prompt(wing_id, phase_id)

    def get_response(self, wing_id: str, phase_id: str, user_message: str) -> str:
        """Match a template response based on wing, phase, and message keywords."""
        canonical_id = self.normalize_wing_id(wing_id)
        if not canonical_id:
            return f"Unknown wing: {wing_id}"

        wing = self.templates.get("wings", {}).get(canonical_id)
        if not wing:
            return self._get_mandate_response(canonical_id, phase_id, user_message)

        phase_data = wing.get("phases", {}).get(phase_id)
        if not phase_data:
            return f"No data available for {self.get_wing_name(canonical_id)} in this phase."

        responses = phase_data.get("responses", {})
        message_lower = user_message.lower()

        keyword_map = {
            "status": ["status", "sitrep", "situation", "update", "report"],
            "actions": ["actions", "plan", "doing", "tasks", "activities", "operations"],
            "resources": ["resources", "needs", "requirements", "supplies", "equipment"],
            "coordination": ["coordination", "coordinate", "liaison", "inter-wing", "partner"],
            "challenges": ["challenges", "problems", "issues", "obstacles", "difficulties"],
        }

        for response_key, keywords in keyword_map.items():
            if any(kw in message_lower for kw in keywords) and response_key in responses:
                return responses[response_key]

        greetings = ["hello", "hi", "assalam", "salam", "greetings", "start", "hey", "assalam-u-alaikum"]
        if any(g in message_lower for g in greetings):
            return phase_data.get("greeting", responses.get("default", "Wing activated."))

        return responses.get(
            "default",
            f"{self.get_wing_name(canonical_id)} is operational in this phase.",
        )

    def _get_mandate_response(self, wing_id: str, phase_id: str, user_message: str) -> str:
        wing_name = self.get_wing_name(wing_id)
        actions = self.get_wing_actions(wing_id, phase_id)
        message_lower = user_message.lower()
        if any(g in message_lower for g in ["hello", "hi", "assalam", "salam", "start", "hey"]):
            return f"{wing_name} activated. Focus on your mandate-driven actions for the current phase."
        if actions:
            return f"{wing_name} current priorities: {'; '.join(actions[:3])}."
        return f"{wing_name} is operational in this phase and should respond within its mandate."
