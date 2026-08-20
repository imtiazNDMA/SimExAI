from pathlib import Path

from .database import load_scenario, load_injects

DATA_DIR = Path(__file__).parent.parent / "data"

PHASES = [
    {"id": "d_minus_90", "label": "D-90", "days": "90 days before disaster"},
    {"id": "d_minus_30", "label": "D-30", "days": "30 days before disaster"},
    {"id": "d_day",      "label": "D-Day", "days": "Disaster day"},
    {"id": "d_plus_30",  "label": "D+30", "days": "30 days after disaster"},
    {"id": "d_plus_90",  "label": "D+90", "days": "90 days after disaster"},
]


class ScenarioEngine:
    """State machine for managing SimEx exercise progression."""

    def __init__(
        self,
        scenario_id: str = None,
        injects_id: str = None,
        current_phase_index: int = 0,
    ):
        self.scenario_id = scenario_id
        self.injects_id = injects_id
        self.current_phase_index = max(0, min(current_phase_index, len(PHASES) - 1))
        self.scenario_data = self._load_scenario()
        self.injects_data = self._load_injects()

    def load_scenario(self, scenario_id: str, injects_id: str):
        self.scenario_id = scenario_id
        self.injects_id = injects_id
        self.current_phase_index = 0
        self.scenario_data = self._load_scenario()
        self.injects_data = self._load_injects()

    def _load_scenario(self) -> dict:
        if not self.scenario_id:
            return {}
        return load_scenario(self.scenario_id)

    def _load_injects(self) -> dict:
        if not self.injects_id:
            return {}
        return load_injects(self.scenario_id)

    def get_scenario_info(self) -> dict:
        return {
            "id": self.scenario_data.get("id", self.scenario_id or "no_scenario"),
            "name": self.scenario_data.get("name", "No Scenario Loaded"),
            "type": self.scenario_data.get("type", "N/A"),
            "magnitude": self.scenario_data.get("magnitude", "N/A"),
            "location": self.scenario_data.get("location", "N/A"),
            "impact": self.scenario_data.get("impact", "N/A"),
            "is_uploaded": bool(self.scenario_data.get("is_uploaded")),
            "source_file": self.scenario_data.get("source_file"),
            "source_image_count": self.scenario_data.get("source_image_count", 0),
            "source_visual_page_count": self.scenario_data.get("source_visual_page_count", 0),
            "source_visual_mode": self.scenario_data.get("source_visual_mode", "none"),
            "current_phase": self.get_current_phase()["id"],
        }

    def get_current_phase(self) -> dict:
        return PHASES[self.current_phase_index]

    def get_all_phases(self) -> list[dict]:
        result = []
        for i, phase in enumerate(PHASES):
            result.append({
                **phase,
                "is_active": i == self.current_phase_index,
                "is_completed": i < self.current_phase_index,
            })
        return result

    def advance_phase(self) -> dict | None:
        if self.current_phase_index < len(PHASES) - 1:
            self.current_phase_index += 1
            return self.get_current_phase()
        return None  # Already at final phase

    def go_back_phase(self) -> dict | None:
        if self.current_phase_index > 0:
            self.current_phase_index -= 1
            return self.get_current_phase()
        return None  # Already at first phase

    def reset(self):
        self.current_phase_index = 0

    def reset_to_default(self):
        self.load_scenario(None, None)

    def get_injects_for_phase(self, phase_id: str) -> list[dict]:
        return [
            inject for inject in self.injects_data.get("injects", [])
            if inject["phase_id"] == phase_id
        ]

    def get_current_injects(self) -> list[dict]:
        return self.get_injects_for_phase(self.get_current_phase()["id"])
