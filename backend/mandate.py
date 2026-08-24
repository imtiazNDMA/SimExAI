"""Mandate registry for NDMA wing metadata and phase actions."""
from __future__ import annotations

import json
import re
from functools import cached_property
from pathlib import Path
from typing import Iterable


DATA_DIR = Path(__file__).parent.parent / "data"
MANDATE_PATH = DATA_DIR / "Mandate" / "mandate.json"


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _tokens(value: str) -> set[str]:
    tokens = {_singular(token) for token in _slug(value).split("_") if token}
    return tokens - {"w", "wing"}


def _singular(value: str) -> str:
    if len(value) > 4 and value.endswith("ies"):
        return f"{value[:-3]}y"
    if len(value) > 3 and value.endswith("s"):
        return value[:-1]
    return value


class MandateRegistry:
    """Loads wing mandates and exposes canonical wing metadata."""

    def __init__(self, path: Path = MANDATE_PATH):
        self.path = path

    @cached_property
    def data(self) -> dict:
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    @cached_property
    def wings(self) -> dict:
        return self.data.get("wings", {})

    def get_wings(self) -> list[dict]:
        return [
            {
                "id": wing_id,
                "name": wing.get("name", wing_id),
                "icon": wing.get("icon", "ND"),
                "short_name": wing.get("short_name", wing.get("name", wing_id)),
                "abbreviation": wing.get("abbreviation", ""),
            }
            for wing_id, wing in self.wings.items()
        ]

    def get_wing(self, wing_id: str) -> dict | None:
        canonical_id = self.normalize_wing_id(wing_id)
        if canonical_id is None:
            return None
        return self.wings.get(canonical_id)

    def get_wing_name(self, wing_id: str) -> str:
        wing = self.get_wing(wing_id)
        return wing.get("name", wing_id) if wing else wing_id

    def get_wing_icon(self, wing_id: str) -> str:
        wing = self.get_wing(wing_id)
        return wing.get("icon", "ND") if wing else "ND"

    def get_phase_group(self, phase_id: str) -> str:
        return self.data.get("phase_groups", {}).get(phase_id, "during_disaster")

    def get_phase_responsibilities(self, wing_id: str, phase_id: str) -> list[str]:
        wing = self.get_wing(wing_id)
        if not wing:
            return []
        group = self.get_phase_group(phase_id)
        return wing.get("responsibilities", {}).get(group, [])

    def get_wing_actions(self, wing_id: str, phase_id: str) -> list[str]:
        wing = self.get_wing(wing_id)
        if not wing:
            return []
        phase_actions = wing.get("simex_phase_actions", {}).get(phase_id)
        if phase_actions:
            return phase_actions
        return self.get_phase_responsibilities(wing_id, phase_id)

    def normalize_wing_id(self, value: str | None) -> str | None:
        if not value:
            return None

        candidate = _slug(str(value))
        if candidate in self.wings:
            return candidate

        candidate_tokens = _tokens(str(value))
        if not candidate_tokens:
            return None

        for wing_id, wing in self.wings.items():
            reference_values = [
                wing_id,
                wing.get("name", ""),
                wing.get("short_name", ""),
                wing.get("abbreviation", ""),
            ]
            reference_slugs = [_slug(item) for item in reference_values if item]
            if candidate in reference_slugs:
                return wing_id

            reference_tokens: set[str] = set()
            for item in reference_values:
                reference_tokens.update(_tokens(item))

            if candidate_tokens.issubset(reference_tokens):
                return wing_id

            if len(candidate) > 3 and any(candidate in ref for ref in reference_slugs):
                return wing_id

        return None

    def normalize_wing_ids(self, values: Iterable[str], keep_unknown: bool = True) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values or []:
            wing_id = self.normalize_wing_id(value)
            final_id = wing_id or (str(value) if keep_unknown and value else None)
            if final_id and final_id not in seen:
                normalized.append(final_id)
                seen.add(final_id)
        return normalized

    def format_mandate_for_prompt(self, wing_id: str, phase_id: str) -> str:
        """Return a compact role boundary rather than an exhaustive checklist."""
        wing = self.get_wing(wing_id)
        if not wing:
            return "No mandate found for this wing."

        responsibilities = self.get_phase_responsibilities(wing_id, phase_id)
        phase_actions = wing.get("simex_phase_actions", {}).get(phase_id) or []
        other_wings = [
            f"- {other.get('name', other_id)}: {other.get('mandate_scope', 'Not specified')}"
            for other_id, other in self.wings.items()
            if other_id != wing_id
        ]

        sections = [
            f"Mandate scope: {wing.get('mandate_scope', 'Not specified')}",
            "Current-phase responsibilities:\n" + self._bullets(responsibilities),
        ]
        if phase_actions:
            sections.append(
                "Current-phase exercise actions:\n" + self._bullets(phase_actions)
            )
        sections.extend(
            [
                (
                    "Coordination boundary: keep ownership with this wing. It may produce "
                    "mandated information, decisions, or support for another wing, but do not "
                    "assign it that wing's downstream execution responsibilities."
                ),
                "Other-wing ownership boundaries:\n" + "\n".join(other_wings),
            ]
        )
        return "\n\n".join(sections)

    def _bullets(self, items: Iterable[str]) -> str:
        return "\n".join(f"- {item}" for item in items)
