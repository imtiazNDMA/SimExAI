"""Generate mandate-driven wing_responses.json from data/Mandate/mandate.json."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).parent.parent
MANDATE_PATH = ROOT / "data" / "Mandate" / "mandate.json"
OUTPUT_PATH = ROOT / "data" / "templates" / "wing_responses.json"

PHASE_LABELS = {
    "d_minus_90": "D-90",
    "d_minus_30": "D-30",
    "d_day": "D-Day",
    "d_plus_30": "D+30",
    "d_plus_90": "D+90",
}


def build_templates() -> dict:
    with open(MANDATE_PATH, "r", encoding="utf-8") as f:
        mandate = json.load(f)

    data = {"wings": {}}
    for wing_id, wing in mandate["wings"].items():
        phases = {}
        for phase_id, label in PHASE_LABELS.items():
            actions = wing.get("simex_phase_actions", {}).get(phase_id, [])
            phase_group = mandate.get("phase_groups", {}).get(phase_id, "during_disaster")
            responsibilities = wing.get("responsibilities", {}).get(phase_group, [])
            focus = _first(actions, responsibilities, wing.get("key_functions", []))
            phases[phase_id] = {
                "greeting": (
                    f"{wing['name']} activated for {label}. "
                    f"Apply the wing mandate to the active scenario and injects."
                ),
                "actions": actions,
                "responses": {
                    "status": f"{wing['name']} is tracking {label} priorities: {focus}",
                    "actions": _sentence("Current mandated actions", actions),
                    "resources": (
                        f"{wing['name']} should identify resources, data, partners, approvals, "
                        "and support needed to deliver the phase priorities."
                    ),
                    "coordination": (
                        f"{wing['name']} should coordinate with NEOC, relevant NDMA wings, "
                        "federal and provincial stakeholders, and scenario-specific partners."
                    ),
                    "challenges": (
                        f"{wing['name']} should surface mandate-specific constraints, data gaps, "
                        "resource bottlenecks, and coordination risks for this phase."
                    ),
                    "default": (
                        f"{wing['name']} should respond to the scenario using its mandate, "
                        "phase responsibilities, and active inject priorities."
                    ),
                },
            }

        data["wings"][wing_id] = {
            "name": wing["name"],
            "icon": wing.get("icon", "ND"),
            "phases": phases,
        }

    return data


def _first(*groups: list[str]) -> str:
    for group in groups:
        if group:
            return group[0]
    return "No mandate priority has been defined."


def _sentence(prefix: str, items: list[str]) -> str:
    if not items:
        return f"{prefix}: no specific action list has been defined for this phase."
    clean_items = [item.rstrip(".") for item in items]
    return f"{prefix}: {'; '.join(clean_items)}."


def main() -> None:
    data = build_templates()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print("Updated wing_responses.json from mandate.json")
    print(f"Wings: {len(data['wings'])}")
    for wing_id, wing in data["wings"].items():
        print(f"- {wing_id}: {wing['name']}")


if __name__ == "__main__":
    main()
