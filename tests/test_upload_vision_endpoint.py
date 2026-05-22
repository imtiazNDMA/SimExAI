import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import docx
import fitz
from fastapi.testclient import TestClient

from backend import app as app_module


class FakeUploadLLM:
    def __init__(self):
        self.calls = 0
        self.image_counts = []

    def invoke(self, messages):
        self.calls += 1
        content = messages[1].content
        image_count = sum(
            1
            for item in content
            if isinstance(item, dict) and item.get("type") == "image_url"
        )
        self.image_counts.append(image_count)

        class Result:
            pass

        result = Result()
        result.content = json.dumps(
            {
                "scenario": {
                    "id": "generated_from_upload",
                    "name": f"Vision Smoke Scenario {self.calls}",
                    "type": "Flood",
                    "magnitude": "Severe",
                    "location": "Test District",
                    "impact": "Visual map evidence shows affected roads",
                    "context": "Created from attached visual page evidence.",
                    "phases": {
                        "d_day": "Day 0",
                        "d1_to_d5": "Days 1-5",
                        "d5_to_d10": "Days 5-10",
                        "d10_to_d20": "Days 10-20",
                        "d20_to_d50": "Days 20-50",
                    },
                },
                "injects": [
                    {
                        "id": "inj_1",
                        "phase_id": "d_day",
                        "time_offset": "H+2HRS",
                        "title": "Visual evidence inject",
                        "description": "Use observed visual map evidence from the uploaded page.",
                        "severity": "HIGH",
                        "status": "pending",
                        "required_wings": ["w_neoc"],
                    }
                ],
            }
        )
        return result


class UploadVisionEndpointTests(unittest.TestCase):
    def test_pdf_and_docx_uploads_send_visual_pages_to_llm(self):
        original_scenario_dir = app_module.SCENARIO_DIR
        original_inject_dir = app_module.INJECT_DIR
        original_upload_llm = app_module.responder.upload_llm
        original_load_scenario = app_module.scenario.load_scenario
        original_get_scenario_info = app_module.scenario.get_scenario_info
        original_get_all_phases = app_module.scenario.get_all_phases
        original_get_current_injects = app_module.scenario.get_current_injects

        fake_llm = FakeUploadLLM()
        try:
            app_module.responder.upload_llm = fake_llm
            app_module.scenario.load_scenario = lambda _scenario_id, _injects_id: None
            app_module.scenario.get_scenario_info = lambda: {"id": "vision_smoke", "is_uploaded": True}
            app_module.scenario.get_all_phases = lambda: []
            app_module.scenario.get_current_injects = lambda: []

            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp = Path(tmp_dir)
                app_module.SCENARIO_DIR = tmp / "scenarios"
                app_module.INJECT_DIR = tmp / "injects"
                pdf_path = tmp / "sample.pdf"
                docx_path = tmp / "sample.docx"
                self._write_pdf(pdf_path, "PDF visual smoke page")
                self._write_docx(docx_path, "DOCX visual smoke page")

                with patch(
                    "backend.document_parser._convert_docx_to_pdf_with_word",
                    side_effect=lambda _docx_path, pdf_path: self._write_pdf(pdf_path, "Rendered DOCX page"),
                ):
                    with TestClient(app_module.app) as client:
                        for upload_path in (pdf_path, docx_path):
                            with upload_path.open("rb") as handle:
                                response = client.post(
                                    "/api/scenario/upload",
                                    files={"file": (upload_path.name, handle)},
                                )
                            self.assertEqual(response.status_code, 200)
                            self.assertIn("successfully", response.json()["message"])

                scenarios = list((tmp / "scenarios").glob("*.json"))
                injects = list((tmp / "injects").glob("*.json"))
                self.assertEqual(len(scenarios), 2)
                self.assertEqual(len(injects), 2)
                self.assertEqual(fake_llm.image_counts, [1, 1])
                for scenario_path in scenarios:
                    scenario_data = json.loads(scenario_path.read_text(encoding="utf-8"))
                    self.assertEqual(scenario_data["source_visual_page_count"], 1)
                    self.assertEqual(scenario_data["source_visual_mode"], "full_page")
        finally:
            app_module.SCENARIO_DIR = original_scenario_dir
            app_module.INJECT_DIR = original_inject_dir
            app_module.responder.upload_llm = original_upload_llm
            app_module.scenario.load_scenario = original_load_scenario
            app_module.scenario.get_scenario_info = original_get_scenario_info
            app_module.scenario.get_all_phases = original_get_all_phases
            app_module.scenario.get_current_injects = original_get_current_injects

    def _write_pdf(self, path: Path, text: str) -> None:
        pdf_doc = fitz.open()
        page = pdf_doc.new_page()
        page.insert_text((72, 72), text)
        path.write_bytes(pdf_doc.tobytes())
        pdf_doc.close()

    def _write_docx(self, path: Path, text: str) -> None:
        document = docx.Document()
        document.add_paragraph(text)
        document.save(path)


if __name__ == "__main__":
    unittest.main()
