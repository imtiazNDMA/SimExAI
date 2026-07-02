---
name: SimEx Backend Development
description: Backend engineering guide for the SimEx AI chatbot — FastAPI project structure, scenario engine, template/LLM response system, REST API design, and JSON data layer.
---

# SimEx Backend Development

Instructions for building and maintaining the SimEx AI backend.

## Technology Stack

| Component | Technology | Notes |
|---|---|---|
| **Framework** | FastAPI | Async Python web framework |
| **Python** | 3.14+ | As per `pyproject.toml` |
| **Data Layer** | JSON files | No database for MVP |
| **Response Engine** | Template-based | Future: Ollama LLM plugin |
| **Server** | Uvicorn | ASGI server |

## Project Structure

```
backend/
├── app.py              # FastAPI application, routes, CORS
├── scenario_engine.py  # Phase state machine, scenario loading
├── template_engine.py  # Template response lookup (→ future: Ollama)
└── models.py           # Pydantic data models
```

## Core Architecture

### Scenario Engine (`scenario_engine.py`)

The scenario engine manages exercise state:

```python
# State Machine: Phases flow in order
PHASES = [
    {"id": "d_minus_90",  "label": "D-90",   "days": "Day -90"},
    {"id": "d_minus_30",  "label": "D-30",   "days": "Day -30"},
    {"id": "d_day",       "label": "D-Day",  "days": "Day 0"},
    {"id": "d_plus_30",   "label": "D+30",   "days": "Day +30"},
    {"id": "d_plus_90",   "label": "D+90",   "days": "Day +90"},
]
```

Key methods:
- `load_scenario(scenario_id)` → Load scenario JSON from `data/scenarios/`
- `get_current_phase()` → Return current phase object
- `advance_phase()` → Move to next phase
- `get_injects_for_phase(phase_id)` → Return scenario injects for the phase

### Template Engine (`template_engine.py`)

MVP uses static template responses. Designed for easy swap to Ollama:

```python
class TemplateEngine:
    """MVP: Returns pre-written template responses.
    Future: Replace with OllamaEngine that calls local LLM."""
    
    def get_response(self, wing_id: str, phase_id: str, user_message: str) -> str:
        # Look up in data/templates/wing_responses.json
        ...

# Future interface (same method signature):
class OllamaEngine:
    def get_response(self, wing_id: str, phase_id: str, user_message: str) -> str:
        # Call Ollama API with wing persona + scenario context
        ...
```

### API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/scenario` | Get current scenario details |
| `GET` | `/api/phases` | List all phases with current active phase |
| `POST` | `/api/phase/advance` | Advance to next phase |
| `GET` | `/api/wings` | List all NDMA wings |
| `GET` | `/api/wings/{wing_id}/actions` | Get wing actions for current phase |
| `POST` | `/api/chat` | Send message, get wing-specific response |
| `GET` | `/api/injects` | Get injects for current phase |

### Chat Request/Response

```json
// POST /api/chat
{
    "wing_id": "operations_logistic",
    "phase_id": "d_minus_90",
    "message": "What is the current situation?"
}

// Response
{
    "wing_id": "operations_logistic",
    "wing_name": "Operations and Logistic Wing (Ops & Log)",
    "phase_id": "d_minus_90",
    "response": "NEOC activated to 24/7 operations. First SitRep issued...",
    "timestamp": "2026-03-05T06:30:00Z"
}
```

## Data Files

All data lives in `data/` as JSON:

- `data/scenarios/earthquake_batagram_7_4.json` — Scenario definition
- `data/templates/wing_responses.json` — Template responses (10 wings × 5 phases)
- `data/injects/earthquake_injects.json` — Timed scenario inject events

## Running the Backend

```bash
cd backend
uvicorn app:app --reload --port 8000
```

## Adding Ollama Support (Future)

When ready to replace templates with LLM:
1. Create `ollama_engine.py` implementing the same `get_response()` interface
2. Add `RESPONSE_ENGINE=ollama` environment variable
3. In `app.py`, swap `TemplateEngine` for `OllamaEngine` based on env var
4. Wing persona prompts go in `data/prompts/` directory
