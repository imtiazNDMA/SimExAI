---
name: SimEx Data and Prompts
description: Data management and prompt engineering guide for SimEx AI — template responses, scenario data schemas, wing personas, inject events, and LM Studio prompt construction.
---

# SimEx Data & Prompts

Instructions for managing scenario data, template responses, and future LLM prompts for the SimEx AI system.

## Data Directory Structure

```
data/
├── scenarios/
│   └── earthquake_batagram_7_4.json   # Scenario definition
├── templates/
│   └── wing_responses.json            # 9 wings x 5 phases responses
├── injects/
│   └── earthquake_injects.json        # Timed scenario events
└── Mandate/mandate.json               # Wing mandates (source of prompt context)
    ├── moderator_system.md
    └── wing_personas/
        ├── technical_early_warning.md
        ├── operations_logistic.md
        └── ...
```

## JSON Schemas

### Scenario Schema (`scenarios/*.json`)

```json
{
    "id": "earthquake_batagram_7_4",
    "name": "Earthquake — Batagram KP M7.4",
    "type": "earthquake",
    "magnitude": 7.4,
    "location": {
        "district": "Batagram",
        "province": "Khyber Pakhtunkhwa",
        "coordinates": { "lat": 34.68, "lon": 73.02 }
    },
    "impact": {
        "estimated_fatalities": "2000-5000",
        "estimated_injuries": "10000-25000",
        "displaced": "80000-150000",
        "houses_damaged": "30000-60000"
    },
    "phases": [
        { "id": "d_minus_90", "label": "D-90", "days": "Day -90" },
        { "id": "d_minus_30", "label": "D-30", "days": "Day -30" },
        { "id": "d_day", "label": "D-Day", "days": "Day 0" },
        { "id": "d_plus_30", "label": "D+30", "days": "Day +30" },
        { "id": "d_plus_90", "label": "D+90", "days": "Day +90" }
    ]
}
```

### Wing Responses Schema (`templates/wing_responses.json`)

```json
{
    "wings": {
        "technical_early_warning": {
            "name": "Technical Early Warning Wing (Tech EW)",
            "icon": "EW",
            "phases": {
                "d_minus_90": {
                    "greeting": "Tech Early Warning Wing activated...",
                    "actions": ["Issue earthquake alert...", "..."],
                    "responses": {
                        "status": "Seismic monitoring active...",
                        "situation": "M7.4 earthquake detected...",
                        "default": "Tech Early Warning is monitoring..."
                    }
                }
            }
        }
    }
}
```

### Injects Schema (`injects/*.json`)

```json
{
    "scenario_id": "earthquake_batagram_7_4",
    "injects": [
        {
            "id": "inject_001",
            "phase_id": "d_minus_90",
            "time_offset": "+2h",
            "title": "Aftershock M5.8",
            "description": "A M5.8 aftershock causes secondary collapse...",
            "severity": "critical",
            "target_wings": ["operations_logistic", "technical_early_warning"],
            "response_required": true
        }
    ]
}
```

## Template Response Matching

The MVP uses keyword-based matching to select responses:

```python
def match_response(wing_responses, user_message):
    message_lower = user_message.lower()
    for keyword, response in wing_responses.items():
        if keyword in message_lower:
            return response
    return wing_responses.get("default", "No response available.")
```

Keywords to support per wing:
- `status` / `sitrep` — Current situation report
- `actions` / `plan` — What the wing is doing
- `resources` / `needs` — Resource requirements
- `coordination` — Inter-wing coordination
- `challenges` — Current obstacles
- `default` — Fallback response

## Prompt Construction

Prompts are built in `backend/llm_engine.py` (not stored as files). Each wing's mandate is injected into the Invigilator system prompt:

```markdown
# System Prompt: Operations and Logistic Wing (Ops & Log)

You are the Operations and Logistic Wing of NDMA Pakistan, responding during 
a magnitude 7.4 earthquake simulation exercise in Batagram, KP.

## Current Phase: {phase_label}
## Scenario Context: {scenario_summary}

Your responsibilities:
- {phase_specific_actions}

Respond as a professional disaster operations coordinator.
Keep responses focused, actionable, and within your wing's mandate.
Reference real NDMA procedures and terminology.
```

## Adding New Scenarios

To add a new disaster scenario:
1. Create `data/scenarios/{scenario_id}.json` following the schema
2. Create `data/templates/wing_responses_{scenario_id}.json` with wing responses
3. Create `data/injects/{scenario_id}_injects.json` with inject events
4. Update the backend to load the new scenario
