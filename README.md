# SimEx AI — NDMA Simulation Exercise Chatbot

An AI-powered chatbot for moderating and conducting dynamic disaster simulation exercises (SimEx) for NDMA Pakistan.

## Overview

SimEx AI acts as the **Lead Moderator/Invigilator**. Instead of hardcoding a specific disaster, the application allows Exercise Controllers to upload raw, multi-page Scenario Documents (PDFs or Word Docs). The AI automatically reads the document, extracts the scenario details, generates chronological phase injects, and stores the knowledge in a Pinecone Vector Database.

Participants then select their NDMA Wing and chat with the AI. The AI evaluates their responses, tests their operational readiness based on their specific mandate, and challenges them with scenario injects using Retrieval-Augmented Generation (RAG).

## Key Features

- **Dynamic Document Ingestion:** Upload any disaster scenario (Flood, Earthquake, Cyclone).
- **Massive Document Chunking Pipeline:** Capable of processing 50+ page documents by chunking text and vision (images/maps) into batches to prevent AI payload crashes.
- **Exhaustive Inject Extraction:** Automatically generates highly detailed injects aligned with 5 operational phases.
- **Pure Pinecone RAG Architecture:** Fully relies on Pinecone for semantic search and AI context retrieval. No local vector stores.
- **SQLite Data Layer:** Scenario metadata and injects are safely stored in a zero-dependency local SQLite database (`data/simex.db`).
- **Strict Invigilator Persona:** The AI does not solve the disaster for the participants. It explicitly challenges them to respond based on their Wing's mandate.

## Architecture

```
backend/
├── app.py               # FastAPI server, API routes, Upload Pipeline
├── llm_engine.py        # LangChain ChatOpenAI -> LM Studio & Invigilator prompt
├── document_parser.py   # PDF/DOCX text and Vision extraction
├── database.py          # SQLite database connection & CRUD operations
└── pinecone_engine.py   # Pure Pinecone Vector Search integration

frontend/                # Vanilla HTML/JS/CSS (Chat UI, Timeline, Dashboard)
data/simex.db            # Generated SQLite Database
```

## NDMA Wings (10)

Tech Early Warning · Ops Wing · Logistics · DRR · GCC · PCC · Tech E&M · Military & Media · NIDM · Infra Audit

## Timeline Phases (5)

D-90 → D-30 → D-Day → D+30 → D+90

## Quick Start

### Prerequisites
- Python 3.10+
- `uv` package manager
- Copy `.env.example` to `.env` and configure your API keys and settings:
  - Pinecone API Key (`PINECONE_API_KEY`)
  - LM Studio running locally with an OpenAI-compatible server
    (Default: `http://localhost:1234/v1`, model `google/gemma-4-26b-a4b`).
    Start it from LM Studio's Developer / Local Server tab and load the model.

### Installation & Run

**One command (Windows):**

```bat
start.bat
```

This checks prerequisites, creates `.env` from `.env.example` if missing, runs `uv sync`,
verifies the configured LLM server is reachable, starts the backend, and opens
http://localhost:9897 once it responds.

Options (passed through to `start.ps1`):

| Flag | Effect |
| --- | --- |
| `-Port 8080` | Run on a different port (default 9897) |
| `-NoSync` | Skip `uv sync` for fast restarts |
| `-NoBrowser` | Don't open the browser |

**Manual:**

```bash
# Install dependencies
uv sync

# Start backend server
uv run uvicorn backend.app:app --reload --port 9897

# Access the application
# Open http://localhost:9897 in your browser
```