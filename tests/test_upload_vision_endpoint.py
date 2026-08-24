"""Upload pipeline smoke test.

Verifies that a PDF and a DOCX upload each reach the LLM with their rendered
full-page images attached, and that the extracted scenario is persisted.

Originally written against the JSON-file storage layer and a synchronous LLM
call. Adapted for the current architecture: SQLite persistence (commit
4a7d26e), the async `ainvoke` upload path, and the D-90..D+90 phase scheme.
"""
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import docx
import fitz
from fastapi.testclient import TestClient

from backend import app as app_module
from backend import database


class FakeUploadLLM:
    """Stands in for the LM Studio client, recording what it was sent.

    The real upload path awaits `ainvoke`, so this must be async.
    """

    def __init__(self):
        self.calls = 0
        self.image_counts = []
        self.system_contents = []

    async def ainvoke(self, messages):
        self.calls += 1
        self.system_contents.append(messages[0].content)
        content = messages[1].content
        self.image_counts.append(
            sum(
                1
                for item in content
                if isinstance(item, dict) and item.get("type") == "image_url"
            )
        )

        class Result:
            pass

        result = Result()
        # Returned as a raw JSON string, exactly as the model would emit it.
        result.content = (
            '{"scenario": {'
            '"id": "generated_from_upload",'
            f'"name": "Vision Smoke Scenario {self.calls}",'
            '"type": "Flood",'
            '"magnitude": "Severe",'
            '"location": "Test District",'
            '"impact": "Visual map evidence shows affected roads",'
            '"context": "Created from attached visual page evidence."'
            '}, "injects": [{'
            '"id": "inj_1",'
            '"phase_id": "d_day",'
            '"time_offset": "H+2HRS",'
            '"title": "Visual evidence inject",'
            '"description": "Use observed visual map evidence from the uploaded page.",'
            '"severity": "HIGH",'
            '"status": "pending",'
            '"required_wings": ["operations_logistic"]'
            '}]}'
        )
        return result


class FakeResponder:
    def __init__(self, upload_llm):
        self.upload_llm = upload_llm

    @staticmethod
    def format_llm_error(exc):
        return str(exc)


class UploadVisionEndpointTests(unittest.TestCase):
    def setUp(self):
        # Isolate the database so the test never touches data/simex.db.
        # Kept outside the repo: database.get_connection() commits but never
        # closes (review P2-3), so Windows may hold the file handle and leave
        # the directory behind. Task 1.6 fixes that at the source.
        self.tmp = Path(tempfile.mkdtemp(prefix="simexai_test_"))

        self._original_db_path = database.DB_PATH
        database.DB_PATH = self.tmp / "test.db"
        database.init_db()

        self.fake_llm = FakeUploadLLM()
        self._original_build_responder = app_module._build_responder
        app_module._build_responder = lambda _scenario: FakeResponder(self.fake_llm)

        # The upload path indexes into Pinecone; keep the test offline.
        self._original_vector_store = app_module.vector_store
        app_module.vector_store = None

    def tearDown(self):
        app_module._build_responder = self._original_build_responder
        app_module.vector_store = self._original_vector_store
        database.DB_PATH = self._original_db_path

        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_pdf_and_docx_uploads_send_visual_pages_to_llm(self):
        pdf_path = self.tmp / "sample.pdf"
        docx_path = self.tmp / "sample.docx"
        self._write_pdf(pdf_path, "PDF visual smoke page")
        self._write_docx(docx_path, "DOCX visual smoke page")

        with patch(
            "backend.document_parser._convert_docx_to_pdf_with_word",
            side_effect=lambda _docx_path, out_pdf: self._write_pdf(out_pdf, "Rendered DOCX page"),
        ):
            with TestClient(app_module.app) as client:
                headers = {"X-Session-Id": "11111111-1111-4111-8111-111111111111"}
                session = client.post("/api/session", headers=headers)
                self.assertEqual(session.status_code, 200)
                self.assertEqual(session.json()["role"], "controller")
                for upload_path in (pdf_path, docx_path):
                    with upload_path.open("rb") as handle:
                        response = client.post(
                            "/api/scenario/upload",
                            headers=headers,
                            files={"file": (upload_path.name, handle)},
                        )
                    # Extraction runs in the background; the POST only hands
                    # back a job id.
                    self.assertEqual(response.status_code, 202)
                    job_id = response.json()["job_id"]

                    deadline = time.time() + 30
                    while time.time() < deadline:
                        job = client.get(
                            f"/api/scenario/upload/{job_id}", headers=headers
                        ).json()
                        if job["done"]:
                            break
                        time.sleep(0.05)

                    self.assertTrue(job["done"], "upload job did not finish in time")
                    self.assertIsNone(job["error"])
                    self.assertIn("successfully", job["result"]["message"])

        # Each upload is a single page, so each LLM call carries exactly one image.
        self.assertEqual(self.fake_llm.image_counts, [1, 1])
        self.assertNotIn("{wing_ids}", self.fake_llm.system_contents[0])
        self.assertIn("operations_logistic", self.fake_llm.system_contents[0])

        with database.get_connection() as conn:
            scenarios = conn.execute(
                "SELECT id, source_visual_page_count, source_visual_mode FROM scenarios"
            ).fetchall()
            inject_count = conn.execute("SELECT COUNT(*) FROM injects").fetchone()[0]
            exercise = conn.execute(
                "SELECT scenario_id, current_phase_index FROM exercises"
            ).fetchone()

        self.assertEqual(len(scenarios), 2, "one scenario row per upload")
        for row in scenarios:
            self.assertEqual(row["source_visual_page_count"], 1)
            self.assertEqual(row["source_visual_mode"], "full_page")

        self.assertEqual(inject_count, 2, "one inject per upload")
        self.assertEqual(exercise["scenario_id"], job["result"]["scenario"]["id"])
        self.assertEqual(exercise["current_phase_index"], 0)

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
