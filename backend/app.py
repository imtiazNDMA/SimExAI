"""SimEx AI Backend — FastAPI application."""
from datetime import datetime, timezone
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import json
import re
import shutil
import uuid

from .models import ChatRequest, ChatResponse
from .ollama_engine import OllamaEngine
from .scenario_engine import PHASES, ScenarioEngine
from .document_parser import parse_document
from .mandate import MandateRegistry
from .vector_store import VectorStore

from dotenv import load_dotenv
load_dotenv()


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
try:
    vector_store = VectorStore()
    responder.set_vector_store(vector_store)
except Exception as e:
    print(f"Warning: Could not initialize VectorStore: {e}")
    vector_store = None

DATA_DIR = Path(__file__).parent.parent / "data"
SCENARIO_DIR = DATA_DIR / "scenarios"
INJECT_DIR = DATA_DIR / "injects"
PHASE_IDS = {phase["id"] for phase in PHASES}
mandates = MandateRegistry()

@app.on_event("startup")
def index_default_scenario():
    """Index the default scenario into Pinecone on first startup."""
    if vector_store is None:
        return
    try:
        vector_store.index_scenario(scenario.scenario_id, scenario.scenario_data)
        vector_store.index_injects(
            scenario.scenario_id, scenario.injects_data.get("injects", [])
        )
        print(f"Indexed default scenario: {scenario.scenario_id}")
    except Exception as e:
        print(f"Warning: Could not index default scenario: {e}")


def _slugify(value: str | None, fallback: str = "uploaded_scenario") -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (value or "").lower()).strip("_")
    return slug or fallback


def _read_upload_as_context(file: UploadFile) -> dict:
    """Parse an upload through a temporary file and remove it immediately."""
    safe_name = Path(file.filename or "scenario").name
    tmp_dir = Path(__file__).parent / f"simexai_upload_{uuid.uuid4().hex}"
    tmp_dir.mkdir(parents=True, exist_ok=False)
    try:
        file_path = tmp_dir / safe_name
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        return parse_document(file_path)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _clean_llm_json(raw: str) -> str:
    """Remove common LLM artifacts that break JSON parsing."""
    # Remove lines that are just ellipsis / placeholder comments
    lines = raw.splitlines()
    cleaned_lines = []
    for line in lines:
        stripped = line.strip().rstrip(",")
        # Skip lines like: ... , "... more items", // comments, etc.
        if stripped in ("", "...", "…") or stripped.startswith("...") or stripped.startswith("…"):
            continue
        cleaned_lines.append(line)
    raw = "\n".join(cleaned_lines)
    # Remove single-line // comments (not inside strings — best-effort)
    raw = re.sub(r'(?m)^(\s*)//.*$', '', raw)
    # Remove trailing commas before } or ]
    raw = re.sub(r',\s*([}\]])', r'\1', raw)
    return raw


def _parse_llm_json(raw_output: str) -> dict:
    # 1) Try raw output directly
    try:
        return json.loads(raw_output)
    except json.JSONDecodeError:
        pass

    # 2) Extract from markdown code fences if present
    json_str = raw_output
    json_match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw_output, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)

    # 3) Extract outermost { … }
    start_idx = json_str.find("{")
    end_idx = json_str.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        json_str = json_str[start_idx:end_idx + 1]

    # 4) Clean LLM artifacts (ellipsis lines, trailing commas, comments)
    json_str = _clean_llm_json(json_str)

    # 5) Try parsing the cleaned string
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    # 6) Fall back to json_repair for anything still broken
    import json_repair
    parsed = json_repair.loads(json_str)
    return json.loads(parsed) if isinstance(parsed, str) else parsed


def _scenario_id_for_upload(scenario_data: dict, filename: str | None) -> str:
    name = scenario_data.get("name") or Path(filename or "").stem
    slug = _slugify(str(name), fallback="uploaded_scenario")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return f"{slug}_{timestamp}"


def _normalize_injects(injects: list, scenario_id: str) -> list[dict]:
    normalized = []
    for index, item in enumerate(injects if isinstance(injects, list) else [], start=1):
        if not isinstance(item, dict):
            continue

        phase_id = item.get("phase_id") if item.get("phase_id") in PHASE_IDS else "d_day"
        item["id"] = item.get("id") or f"{scenario_id}_inj_{index:02d}"
        item["phase_id"] = phase_id
        item["time_offset"] = item.get("time_offset") or "TBD"
        item["title"] = item.get("title") or f"Inject {index}"
        item["description"] = item.get("description") or "Scenario-derived inject."
        item["severity"] = str(item.get("severity") or "MEDIUM").upper()
        item["status"] = item.get("status") or "pending"
        item["required_wings"] = mandates.normalize_wing_ids(
            item.get("required_wings") or item.get("target_wings") or []
        )
        normalized.append(item)
    return normalized


def _build_upload_user_content(parsed_data: dict) -> list[dict]:
    extracted_text = parsed_data.get("text", "")
    image_count = parsed_data.get("image_count", 0)
    vision_images = parsed_data.get("vision_images") or []
    visual_page_count = parsed_data.get("visual_page_count", len(vision_images))
    visual_labels = [
        str(item.get("label") or f"Page {index}")
        for index, item in enumerate(vision_images, start=1)
        if isinstance(item, dict)
    ]
    visual_summary = "\n".join(f"- {label}" for label in visual_labels) or "- None"
    text_context = extracted_text or "[No machine-readable text was extracted from this upload.]"

    content = [
        {
            "type": "text",
            "text": (
                "Here is the extracted upload context and full-page visual context.\n\n"
                f"Extracted text:\n{text_context}\n\n"
                f"Embedded images detected in the source document: {image_count}\n"
                f"Full-page visual images attached: {visual_page_count}\n"
                f"Attached visual pages:\n{visual_summary}\n\n"
                "Use both the extracted text and every attached page image. Inspect maps, "
                "tables, charts, scanned content, diagrams, visible damage indicators, "
                "timelines, captions, labels, and page layout when creating the scenario "
                "summary and injects. If text and visuals conflict, prefer concrete "
                "visible evidence from the page images and note it in the generated "
                "scenario context without mentioning implementation details.\n\n"
                "Parse this and output the required JSON."
            ),
        }
    ]

    for index, item in enumerate(vision_images, start=1):
        if not isinstance(item, dict) or not item.get("data"):
            continue
        label = item.get("label") or f"Page {index}"
        mime_type = item.get("mime_type") or "image/jpeg"
        content.append({"type": "text", "text": f"Visual page attachment: {label}"})
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{item['data']}"},
            }
        )

    return content


# ── API Routes ──────────────────────────────────────────────


@app.post("/api/scenario/upload")
async def upload_scenario(file: UploadFile = File(...)):
    """Use an uploaded file as LLM context and persist generated JSON only."""
    from langchain_core.messages import HumanMessage, SystemMessage

    wing_ids = ", ".join(mandates.wings.keys())
    system_msg = SystemMessage(content=f'''You are an expert disaster management planner. 
Use the uploaded scenario document as context. Create one scenario summary and phase injects from that document only.
Use both the extracted text and the attached full-page visual images. The visuals may contain maps, tables, charts, scanned content, diagrams, damage indicators, timelines, captions, and page layout clues that are not present in extracted text.
Output ONLY valid JSON that matches this structure. No markdown formatting ticks around the JSON.
Use only these canonical required_wings ids when assigning injects: {wing_ids}.
{{
  "scenario": {{
    "id": "generated_from_upload",
    "name": "Generated Scenario",
    "type": "Disaster Type",
    "magnitude": "Severity/Intensity",
    "location": "Location string",
    "impact": "Brief impact description",
    "context": "Context description",
    "phases": {{
        "d_day": "D Day timeframe",
        "d1_to_d5": "Days 1-5 timeframe",
        "d5_to_d10": "Days 5-10 timeframe",
        "d10_to_d20": "Days 10-20 timeframe",
        "d20_to_d50": "Days 20-50 timeframe"
    }}
  }},
  "injects": [
    {{
      "id": "inj_1",
      "phase_id": "d_day",
      "time_offset": "H+2HRS",
      "title": "Inject title",
      "description": "inject description",
      "severity": "HIGH",
      "status": "pending",
      "required_wings": ["technical_early_warning", "operations_logistic"]
    }}
  ]
}}
Generate at least 10 injects total, spread across all five phase_ids: "d_day", "d1_to_d5", "d5_to_d10", "d10_to_d20", "d20_to_d50".
Do NOT include ellipsis, placeholder comments, or "..." in the JSON output. Every inject must be a complete JSON object.''')
    raw_output = "No raw output generated"

    try:
        parsed_data = _read_upload_as_context(file)
        image_count = parsed_data.get("image_count", 0)
        visual_page_count = parsed_data.get("visual_page_count", 0)
        visual_mode = parsed_data.get("visual_mode", "none")
        user_msg = HumanMessage(content=_build_upload_user_content(parsed_data))

        try:
            llm_res = responder.upload_llm.invoke([system_msg, user_msg])
        except Exception as exc:
            return {
                "message": f"Failed to process upload: {responder.format_llm_error(exc)}",
                "phases": scenario.get_all_phases(),
            }
        raw_output = llm_res.content
        parsed_json = _parse_llm_json(raw_output)
        if not isinstance(parsed_json, dict):
            raise ValueError("LLM output was not a JSON object")

        scenario_data = parsed_json.get("scenario") or {}
        if not isinstance(scenario_data, dict):
            scenario_data = {}
        scenario_id = _scenario_id_for_upload(scenario_data, file.filename)
        injects_id = f"{scenario_id}_injects"
        injects_list = _normalize_injects(parsed_json.get("injects") or [], scenario_id)

        scenario_data["id"] = scenario_id
        scenario_data["is_uploaded"] = True
        scenario_data["source_file"] = Path(file.filename or "scenario").name
        scenario_data["source_image_count"] = image_count
        scenario_data["source_visual_page_count"] = visual_page_count
        scenario_data["source_visual_mode"] = visual_mode

        scenario_path = SCENARIO_DIR / f"{scenario_id}.json"
        injects_path = INJECT_DIR / f"{injects_id}.json"
        SCENARIO_DIR.mkdir(parents=True, exist_ok=True)
        INJECT_DIR.mkdir(parents=True, exist_ok=True)

        with open(scenario_path, "w", encoding="utf-8") as f:
            json.dump(scenario_data, f, indent=4)
        
        with open(injects_path, "w", encoding="utf-8") as f:
            json.dump({"injects": injects_list}, f, indent=4)
            
        if vector_store:
            try:
                vector_store.delete_scenario(scenario_id)
                vector_store.index_scenario(scenario_id, scenario_data)
                vector_store.index_injects(scenario_id, injects_list)
            except Exception as e:
                print(f"Warning: Could not index uploaded scenario: {e}")
    
        scenario.load_scenario(scenario_id, injects_id)
        return {
            "message": "Scenario uploaded and extracted successfully.",
            "scenario": scenario.get_scenario_info(),
            "phases": scenario.get_all_phases(),
            "injects": scenario.get_current_injects(),
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        print("Raw Output:", raw_output)
        return {"message": f"Failed to process upload: {str(e)}", "phases": scenario.get_all_phases()}


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
    """Reset to the default exercise and D Day."""
    scenario.reset_to_default()
    return {
        "message": "Exercise reset to D Day",
        "scenario": scenario.get_scenario_info(),
        "phases": scenario.get_all_phases(),
        "injects": scenario.get_current_injects(),
    }


@app.get("/api/wings")
def get_wings():
    """List all NDMA wings."""
    return {"wings": responder.get_wings()}


@app.get("/api/wings/{wing_id}/actions")
def get_wing_actions(wing_id: str):
    """Get wing actions for current phase."""
    canonical_id = responder.normalize_wing_id(wing_id) or wing_id
    phase = scenario.get_current_phase()
    actions = responder.get_wing_actions(canonical_id, phase["id"])
    return {
        "wing_id": canonical_id,
        "wing_name": responder.get_wing_name(canonical_id),
        "phase": phase,
        "actions": actions,
    }


@app.post("/api/chat")
def chat(request: ChatRequest) -> ChatResponse:
    """Send a message and get a wing-specific response."""
    phase = scenario.get_current_phase()
    wing_id = responder.normalize_wing_id(request.wing_id) or request.wing_id
    response_text = responder.get_response(
        wing_id=wing_id,
        phase_id=request.phase_id if request.phase_id else phase["id"],
        user_message=request.message,
    )

    return ChatResponse(
        wing_id=wing_id,
        wing_name=responder.get_wing_name(wing_id),
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
