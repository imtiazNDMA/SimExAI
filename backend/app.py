"""SimEx AI Backend — FastAPI application."""
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from .models import ChatRequest, ChatResponse
from .ollama_engine import OllamaEngine
from .scenario_engine import ScenarioEngine

app = FastAPI(
    title="SimEx AI",
    description="AI-powered Simulation Exercise Chatbot for NDMA Pakistan",
    version="0.1.0",
)

# CORS for frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize engines
scenario = ScenarioEngine()
responder = OllamaEngine(scenario)


# ── API Routes ──────────────────────────────────────────────


@app.get("/api/scenario")
def get_scenario():
    """Get current scenario details."""
    return scenario.get_scenario_info()


@app.get("/api/phases")
def get_phases():
    """List all phases with active/completed status."""
    return {"phases": scenario.get_all_phases()}


@app.post("/api/phase/advance")
def advance_phase():
    """Advance to the next phase."""
    next_phase = scenario.advance_phase()
    if next_phase is None:
        return {"message": "Already at final phase", "phases": scenario.get_all_phases()}
    return {
        "message": f"Advanced to {next_phase['label']}",
        "current_phase": next_phase,
        "phases": scenario.get_all_phases(),
        "injects": scenario.get_current_injects(),
    }


@app.post("/api/phase/back")
def go_back_phase():
    """Go back to the previous phase."""
    prev_phase = scenario.go_back_phase()
    if prev_phase is None:
        return {"message": "Already at D Day", "phases": scenario.get_all_phases()}
    return {
        "message": f"Returned to {prev_phase['label']}",
        "current_phase": prev_phase,
        "phases": scenario.get_all_phases(),
        "injects": scenario.get_current_injects(),
    }


@app.post("/api/phase/reset")
def reset_phases():
    """Reset to D Day."""
    scenario.reset()
    return {
        "message": "Exercise reset to D Day",
        "phases": scenario.get_all_phases(),
    }


@app.get("/api/wings")
def get_wings():
    """List all NDMA wings."""
    return {"wings": responder.get_wings()}


@app.get("/api/wings/{wing_id}/actions")
def get_wing_actions(wing_id: str):
    """Get wing actions for current phase."""
    phase = scenario.get_current_phase()
    actions = responder.get_wing_actions(wing_id, phase["id"])
    return {
        "wing_id": wing_id,
        "wing_name": responder.get_wing_name(wing_id),
        "phase": phase,
        "actions": actions,
    }


@app.post("/api/chat")
def chat(request: ChatRequest) -> ChatResponse:
    """Send a message and get a wing-specific response."""
    phase = scenario.get_current_phase()
    response_text = responder.get_response(
        wing_id=request.wing_id,
        phase_id=request.phase_id if request.phase_id else phase["id"],
        user_message=request.message,
    )

    return ChatResponse(
        wing_id=request.wing_id,
        wing_name=responder.get_wing_name(request.wing_id),
        phase_id=phase["id"],
        phase_label=phase["label"],
        response=response_text,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/api/injects")
def get_injects():
    """Get inject events for the current phase."""
    phase = scenario.get_current_phase()
    injects = scenario.get_current_injects()
    return {
        "phase": phase,
        "injects": injects,
    }


# ── Static File Serving (production) ───────────────────────

frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
