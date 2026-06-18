"""Vector store service using Pinecone Integrated Inference."""
import os
import json
from typing import List, Dict, Any, Optional

from pinecone import Pinecone
from langchain_text_splitters import RecursiveCharacterTextSplitter


class VectorStore:
    """Manages indexing and retrieval of scenario and injects data using Pinecone."""

    def __init__(self):
        """Connect to Pinecone index (integrated llama-text-embed-v2)."""
        api_key = os.getenv("PINECONE_API_KEY")
        if not api_key:
            raise ValueError("PINECONE_API_KEY environment variable is not set")
            
        self.pc = Pinecone(api_key=api_key)
        index_name = os.getenv("PINECONE_INDEX_NAME", "simexai")
        self.index = self.pc.Index(index_name)
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", ". ", " ", ""]
        )

    def _chunk_scenario(self, scenario_data: Dict[str, Any]) -> List[str]:
        """Convert scenario JSON into chunkable text."""
        # Extract narrative info
        name = scenario_data.get("name", "Scenario")
        disaster_type = scenario_data.get("type", "Disaster")
        magnitude = scenario_data.get("magnitude", "N/A")
        
        # Location info
        loc = scenario_data.get("location", {})
        location_str = "N/A"
        if isinstance(loc, dict):
            location_str = f"{loc.get('district', '')}, {loc.get('province', '')}, {loc.get('country', '')}"
        elif isinstance(loc, str):
            location_str = loc
            
        # Impact info
        impact = scenario_data.get("impact", {})
        impact_str = json.dumps(impact, indent=2) if isinstance(impact, dict) else str(impact)
        
        context = scenario_data.get("context", "")
        
        # Phases info
        phases = scenario_data.get("phases", [])
        phases_str = ""
        if isinstance(phases, list):
            for p in phases:
                if isinstance(p, dict):
                    phases_str += f"- {p.get('label', '')}: {p.get('focus', '')}\n"
        
        # Construct narrative
        narrative = f"""
Scenario Name: {name}
Type: {disaster_type}
Magnitude: {magnitude}
Location: {location_str}

Context:
{context}

Impact Details:
{impact_str}

Phases Overview:
{phases_str}
"""
        return self.text_splitter.split_text(narrative)

    def _inject_to_text(self, inj: Dict[str, Any]) -> str:
        """Convert an inject JSON into a descriptive text block."""
        title = inj.get("title", "Untitled Inject")
        desc = inj.get("description", "No description")
        severity = inj.get("severity", "MEDIUM")
        phase = inj.get("phase_id", "Unknown Phase")
        wings = ", ".join(inj.get("required_wings", inj.get("target_wings", [])))
        
        return f"""
Inject Event: {title}
Severity: {severity}
Phase: {phase}
Target Wings: {wings}

Description:
{desc}
"""

    def index_scenario(self, scenario_id: str, scenario_data: Dict[str, Any]):
        """Chunk scenario text and upsert to Pinecone (auto-embedding)."""
        chunks = self._chunk_scenario(scenario_data)
        
        # Prepare records
        records = []
        for i, chunk in enumerate(chunks):
            records.append({
                "_id": f"{scenario_id}_sc_{i}",
                "text": chunk,
                "category": "scenario",
                "phase_id": "all"
            })
            
        # Upsert with namespace isolation
        if records:
            self.index.upsert_records(namespace=scenario_id, records=records)

    def index_injects(self, scenario_id: str, injects: List[Dict[str, Any]]):
        """Upsert each inject as a record (auto-embedding)."""
        records = []
        for inj in injects:
            text = self._inject_to_text(inj)
            records.append({
                "_id": inj.get("id", f"{scenario_id}_inj_{len(records)}"),
                "text": text,
                "category": "inject",
                "phase_id": inj.get("phase_id", ""),
                "severity": inj.get("severity", "")
            })
            
        if records:
            self.index.upsert_records(namespace=scenario_id, records=records)

    def retrieve(self, query: str, scenario_id: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search using raw text - Pinecone auto-embeds the query."""
        try:
            results = self.index.search(
                namespace=scenario_id,
                query={"inputs": {"text": query}, "top_k": top_k}
            )
            
            hits = results.get("result", {}).get("hits", [])
            # Also handle case if returned as an object directly
            if hasattr(results, "result") and hasattr(results.result, "hits"):
                 hits = results.result.hits
            elif hasattr(results, "hits"):
                 hits = results.hits

            retrieved = []
            for hit in hits:
                # Handle different result structures (dict vs object)
                hit_id = hit.get("_id") if isinstance(hit, dict) else hit.id
                hit_score = hit.get("_score") if isinstance(hit, dict) else hit.score
                
                # Try to get text field from fields
                fields = hit.get("fields", {}) if isinstance(hit, dict) else getattr(hit, "fields", {})
                text = fields.get("text", "") if isinstance(fields, dict) else getattr(fields, "text", "")
                
                if text:
                    retrieved.append({
                        "id": hit_id,
                        "score": hit_score,
                        "text": text
                    })
            return retrieved
        except Exception as e:
            print(f"Vector store retrieval error: {e}")
            return []

    def delete_scenario(self, scenario_id: str):
        """Delete all vectors for a scenario by deleting its namespace."""
        try:
            # Pinecone python SDK allows deleting a whole namespace via delete(delete_all=True, namespace=...)
            # However some versions might not support it directly if not careful.
            # Using basic delete
            self.index.delete(delete_all=True, namespace=scenario_id)
        except Exception as e:
            print(f"Error deleting namespace {scenario_id}: {e}")
