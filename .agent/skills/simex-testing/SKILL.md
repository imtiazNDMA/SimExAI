---
name: SimEx Testing and Deployment
description: Testing patterns, deployment workflow, and environment setup guide for the SimEx AI chatbot system.
---

# SimEx Testing & Deployment

Instructions for testing and deploying the SimEx AI system.

## Environment Setup

### Prerequisites
- Python 3.14+
- `uv` package manager (recommended) or `pip`

### Quick Start

```bash
# Clone and enter project
cd simexAI

# Install dependencies
uv sync
# or: pip install -e .

# Run backend
cd backend
uvicorn app:app --reload --port 9897

# Serve frontend (separate terminal)
cd frontend
python -m http.server 3000
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PINECONE_API_KEY` | _(none)_ | Required for RAG retrieval |
| `PINECONE_INDEX_NAME` | `simexai` | Pinecone index |
| `LMSTUDIO_BASE_URL` | `http://localhost:1234/v1` | LM Studio OpenAI-compatible endpoint |
| `LMSTUDIO_MODEL` | `google/gemma-4-26b-a4b` | Model id as listed by `/v1/models` |
| `LMSTUDIO_MAX_TOKENS` | `3000` | Chat token budget (covers reasoning + answer) |

The active scenario is not an env var — it is whatever was last uploaded, tracked in
`data/simex.db`. The server port is set by the launcher (`start.bat -Port <n>`).

## Testing Patterns

### Manual Testing Checklist

1. **Scenario Load**: Start server → verify `/api/scenario` returns scenario data
2. **Phase Progression**: Call `/api/phase/advance` through all 5 phases
3. **Wing Responses**: For each of the 10 wings:
   - Send "status" → verify wing-specific response
   - Send "actions" → verify phase-specific actions
   - Send "resources" → verify resource needs
4. **Injects**: Verify injects appear for correct phases
5. **Frontend**: 
   - Click each wing → verify chat context switches
   - Send messages → verify responses display
   - Advance phase → verify timeline updates

### API Testing with curl

```bash
# Get scenario info
curl http://localhost:9897/api/scenario

# Get all wings
curl http://localhost:9897/api/wings

# Send a chat message
curl -X POST http://localhost:9897/api/chat \
  -H "Content-Type: application/json" \
  -d '{"wing_id": "ops_wing", "phase_id": "d_minus_90", "message": "What is the current status?"}'

# Advance phase
curl -X POST http://localhost:9897/api/phase/advance

# Get injects for current phase
curl http://localhost:9897/api/injects
```

### Data Validation

```bash
# Validate JSON files
python -c "import json; json.load(open('data/scenarios/earthquake_batagram_7_4.json')); print('✓ Scenario OK')"
python -c "import json; json.load(open('data/templates/wing_responses.json')); print('✓ Templates OK')"
python -c "import json; json.load(open('data/injects/earthquake_injects.json')); print('✓ Injects OK')"
```

## Deployment (Future)

### Docker

```dockerfile
FROM python:3.14-slim
WORKDIR /app
COPY . .
RUN pip install -e .
EXPOSE 9897
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "9897"]
```

### Frontend Serving

In production, serve `frontend/` as static files through FastAPI:

```python
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
```

## Troubleshooting

| Issue | Solution |
|---|---|
| CORS errors in browser | Verify CORS middleware is configured in `app.py` |
| JSON parse errors | Validate data files with `python -c "import json; ..."` |
| Port in use | Change port: `uvicorn app:app --port 8001` |
| Wing not found | Check `wing_id` matches keys in `wing_responses.json` |
