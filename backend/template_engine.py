"""Template response engine — MVP response system.

Loads pre-written responses from JSON and matches based on keywords.
Designed to be swapped with OllamaEngine in the future.
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


class TemplateEngine:
    """Returns template-based responses for wing + phase + keyword combinations.

    Future replacement: OllamaEngine with the same get_response() interface.
    """

    def __init__(self):
        self.templates = self._load_templates()

    def _load_templates(self) -> dict:
        path = DATA_DIR / "templates" / "wing_responses.json"
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_wings(self) -> list[dict]:
        """Return list of all wings with id, name, icon."""
        wings = []
        for wing_id, wing_data in self.templates["wings"].items():
            wings.append({
                "id": wing_id,
                "name": wing_data["name"],
                "icon": wing_data["icon"],
            })
        return wings

    def get_wing_name(self, wing_id: str) -> str:
        wing = self.templates["wings"].get(wing_id, {})
        return wing.get("name", wing_id)

    def get_wing_icon(self, wing_id: str) -> str:
        wing = self.templates["wings"].get(wing_id, {})
        return wing.get("icon", "🏢")

    def get_wing_actions(self, wing_id: str, phase_id: str) -> list[str]:
        """Get action items for a wing in a specific phase."""
        wing = self.templates["wings"].get(wing_id, {})
        phase_data = wing.get("phases", {}).get(phase_id, {})
        return phase_data.get("actions", [])

    def get_response(self, wing_id: str, phase_id: str, user_message: str) -> str:
        """Match a template response based on wing, phase, and message keywords.

        This is the interface that OllamaEngine will also implement.
        """
        wing = self.templates["wings"].get(wing_id)
        if not wing:
            return f"Unknown wing: {wing_id}"

        phase_data = wing.get("phases", {}).get(phase_id)
        if not phase_data:
            return f"No data available for {wing['name']} in this phase."

        responses = phase_data.get("responses", {})
        message_lower = user_message.lower()

        # Keyword matching
        keyword_map = {
            "status": ["status", "sitrep", "situation", "update", "report"],
            "actions": ["actions", "plan", "doing", "tasks", "activities", "operations"],
            "resources": ["resources", "needs", "requirements", "supplies", "equipment"],
            "coordination": ["coordination", "coordinate", "liaison", "inter-wing", "partner"],
            "challenges": ["challenges", "problems", "issues", "obstacles", "difficulties"],
        }

        for response_key, keywords in keyword_map.items():
            if any(kw in message_lower for kw in keywords):
                if response_key in responses:
                    return responses[response_key]

        # Greeting detection
        greetings = ["hello", "hi", "assalam", "salam", "greetings", "start", "hey", "assalam-u-alaikum"]
        if any(g in message_lower for g in greetings):
            return phase_data.get("greeting", responses.get("default", "Wing activated."))

        # Fallback to default
        return responses.get("default", f"{wing['name']} is operational in this phase.")
