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
from .database import init_db, save_scenario, save_injects

from dotenv import load_dotenv
load_dotenv()

# Initialize Database
init_db()


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
PHASE_IDS = {phase["id"] for phase in PHASES}
mandates = MandateRegistry()




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
        # Overwrite whatever the LLM generated to ensure strictly unique numbering across all chunks
        item["id"] = f"{scenario_id}_inj_{index:03d}"
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
    system_msg = SystemMessage(content=f'''You are an expert disaster management planner for NDMA Pakistan. 
Your task is to exhaustively extract EVERY distinct incident, hazard, and required response from the provided scenario document. Do not summarize or compress multiple events into one. If the document describes 40 distinct events across different provinces, you must generate 40 separate injects.

Use both the extracted text and the attached full-page visual images. 
CRITICAL RULES FOR EXTRACTION:
1. Preserve exact quantitative data (e.g., population counts, river names, road km damage) in your inject descriptions. Do not generalize.
2. Align the events chronologically to the correct `phase_id` based on the timeline.
3. Use only these canonical required_wings ids when assigning injects: {{wing_ids}}.

Output ONLY valid JSON that matches this structure. No markdown formatting ticks around the JSON.
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
      "description": "Highly detailed inject description preserving exact numbers and locations.",
      "severity": "HIGH",
      "status": "pending",
      "required_wings": ["technical_early_warning", "operations_logistic"]
    }}
  ]
}}

Do NOT include ellipsis, placeholder comments, or "..." in the JSON output. Every single inject must be a complete JSON object. Ensure the JSON array is properly closed. Output NOTHING except the raw JSON.''')
    raw_output = "No raw output generated"

    try:
        parsed_data = _read_upload_as_context(file)
        extracted_text = parsed_data.get("text", "")
        vision_images = parsed_data.get("vision_images") or []
        image_count = parsed_data.get("image_count", 0)
        visual_page_count = parsed_data.get("visual_page_count", 0)
        visual_mode = parsed_data.get("visual_mode", "none")

        # Chunk the data to prevent payload/OOM crashes
        TEXT_CHUNK_SIZE = 15000
        IMG_CHUNK_SIZE = 5

        text_chunks = []
        if extracted_text:
            for i in range(0, len(extracted_text), TEXT_CHUNK_SIZE):
                text_chunks.append(extracted_text[i:i+TEXT_CHUNK_SIZE])
        else:
            text_chunks = [""]

        img_chunks = []
        if vision_images:
            for i in range(0, len(vision_images), IMG_CHUNK_SIZE):
                img_chunks.append(vision_images[i:i+IMG_CHUNK_SIZE])
        else:
            img_chunks = [[]]

        num_chunks = max(len(text_chunks), len(img_chunks))
        while len(text_chunks) < num_chunks: text_chunks.append("")
        while len(img_chunks) < num_chunks: img_chunks.append([])

        all_injects = []
        scenario_data = {}

        for i in range(num_chunks):
            chunk_parsed_data = {
                "text": text_chunks[i],
                "image_count": image_count if i == 0 else 0, # only count total images in first chunk to avoid prompt confusion
                "vision_images": img_chunks[i],
                "visual_page_count": len(img_chunks[i])
            }
            user_msg = HumanMessage(content=_build_upload_user_content(chunk_parsed_data))

            try:
                # Use ainvoke so we don't completely block the FastAPI event loop for 5 minutes
                llm_res = await responder.upload_llm.ainvoke([system_msg, user_msg])
                raw_output = llm_res.content
                parsed_json = _parse_llm_json(raw_output)
                
                if not isinstance(parsed_json, dict):
                    continue

                if i == 0 or not scenario_data:
                    scen = parsed_json.get("scenario")
                    if isinstance(scen, dict) and scen:
                        scenario_data = scen

                injs = parsed_json.get("injects")
                if isinstance(injs, list):
                    all_injects.extend(injs)

            except Exception as exc:
                print(f"Warning: Chunk {i+1}/{num_chunks} failed: {exc}")
                if i == 0 and num_chunks == 1:
                    return {
                        "message": f"Failed to process upload: {responder.format_llm_error(exc)}",
                        "phases": scenario.get_all_phases(),
                    }

        if not scenario_data:
            scenario_data = {
                "name": "Generated Scenario", "type": "Unknown", "magnitude": "Unknown", 
                "location": "Unknown", "impact": "Unknown", "context": "Failed to extract complete scenario data"
            }

        scenario_id = _scenario_id_for_upload(scenario_data, file.filename)
        injects_id = f"{scenario_id}_injects"
        injects_list = _normalize_injects(all_injects, scenario_id)

        scenario_data["id"] = scenario_id
        scenario_data["is_uploaded"] = True
        scenario_data["source_file"] = Path(file.filename or "scenario").name
        scenario_data["source_image_count"] = image_count
        scenario_data["source_visual_page_count"] = visual_page_count
        scenario_data["source_visual_mode"] = visual_mode
        
        save_scenario(scenario_data)
        save_injects(scenario_id, injects_list)
            
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
