"""Final A8 integration checks for Ashley's Stage 4 handoff."""
from __future__ import annotations

import csv
import json
import re
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REQUIRED_ROOT_FILES = {"rag_system.ipynb", "rag_analysis.md", "requirements.txt", "README.md"}
FORBIDDEN_ARCHIVE_PARTS = {".git", ".venv", "venv", "__pycache__", ".ipynb_checkpoints"}


class FinalIntegrationTests(unittest.TestCase):
    def test_required_submission_files_exist(self):
        self.assertTrue(REQUIRED_ROOT_FILES.issubset({p.name for p in ROOT.iterdir()}))
        self.assertTrue((ROOT / "data" / "cozyday_knowledge_base.json").is_file())
        self.assertTrue((ROOT / "results" / "stage3_evaluations.csv").is_file())
        self.assertTrue((ROOT / "system_architecture.svg").is_file())

    def test_frozen_generation_model_and_five_queries(self):
        from generation import GENERATION_MODEL, DECODING_SETTINGS
        from queries import TEST_QUERIES

        self.assertEqual(GENERATION_MODEL, "Qwen/Qwen2.5-3B-Instruct")
        self.assertEqual(DECODING_SETTINGS["max_new_tokens"], 300)
        self.assertEqual(len(TEST_QUERIES), 5)
        self.assertEqual([q["query_id"] for q in TEST_QUERIES], ["Q1", "Q2", "Q3", "Q4", "Q5"])

    def test_main_grid_has_all_45_rows_and_retrieved_chunks(self):
        with (ROOT / "results" / "stage3_evaluations.csv").open(newline="", encoding="utf-8") as handle:
            rows = [row for row in csv.DictReader(handle) if row["stage"] == "main"]
        self.assertEqual(len(rows), 45)
        combinations = {(r["embedding_key"], r["chunking"]) for r in rows}
        self.assertEqual(len(combinations), 9)
        self.assertTrue(all(r["retrieved_chunk_ids"].strip() for r in rows))
        self.assertTrue(all(r["retrieved_chunk_texts"].strip() for r in rows))
        self.assertTrue(all(r["final_answer"].strip() for r in rows))

    def test_analysis_contains_all_stage4_sections(self):
        text = (ROOT / "rag_analysis.md").read_text(encoding="utf-8")
        for heading in (
            "Cost awareness",
            "RAG vs. fine-tuning vs. pure prompting",
            "Scaling to 10,000 users per day",
            "System architecture",
            "Final integration verification",
        ):
            self.assertIn(heading, text)

    def test_notebook_has_stage4_and_no_saved_errors(self):
        notebook = json.loads((ROOT / "rag_system.ipynb").read_text(encoding="utf-8"))
        sources = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])
        self.assertIn("Stage 4", sources)
        self.assertIn("system_architecture.svg", sources)
        for cell in notebook["cells"]:
            self.assertFalse(any(output.get("output_type") == "error" for output in cell.get("outputs", [])))

    def test_no_machine_specific_paths_or_obvious_secrets(self):
        path_patterns = ("/" + r"Users/[^/]+/", r"[A-Za-z]:\\" + r"Users\\")
        secret_pattern = re.compile(r"(?i)(api[_-]?key|secret|password)\s*=\s*['\"][^'\"]+['\"]")
        suffixes = {".py", ".md", ".txt", ".json", ".ipynb"}
        for path in ROOT.rglob("*"):
            if not path.is_file() or path.suffix not in suffixes:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            self.assertFalse(any(re.search(pattern, text) for pattern in path_patterns), path)
            self.assertIsNone(secret_pattern.search(text), path)

    def test_final_zip_if_present(self):
        archive = ROOT.parent / "Team3-CozyDay-P1-A8.zip"
        if not archive.exists():
            self.skipTest("Final ZIP is created after the source checks pass")
        with zipfile.ZipFile(archive) as zf:
            names = zf.namelist()
        roots = {Path(name).parts[0] for name in names if Path(name).parts}
        self.assertTrue(REQUIRED_ROOT_FILES.issubset(roots))
        self.assertFalse(any(FORBIDDEN_ARCHIVE_PARTS.intersection(Path(name).parts) for name in names))
        self.assertFalse(any(name.endswith((".pt", ".bin", ".safetensors", ".gguf")) for name in names))


if __name__ == "__main__":
    unittest.main(verbosity=2)
