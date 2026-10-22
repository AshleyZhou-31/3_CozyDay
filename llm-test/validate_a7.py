"""Stage 1 regression validator. Never runs inference or writes experiment files.

python llm-test/validate_a7.py [--execute-notebook] [--check-live-prices]
Results execution needs IPython; uses an in-process shell with no kernel sockets.
"""
import argparse
import ast
import hashlib
import io
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest
import types
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
MODULE = ROOT / "llm-test"
sys.path.insert(0, str(MODULE))
import a7_shared as shared
RESULTS = MODULE / "results"

# SHA256 anchors from reviewed commit 36a2e4c; raw files also match dd681be.
# Matrix anchor updated for the reviewed Model 4/5 status-only documentation correction.
BASELINE = {'results/a7_model_1_benchmark.csv': 'b037fa8994da81b098a7d69c3096ed8f26043c7d3749e9226089bc5b4375e000', 'results/a7_model_1_scored.csv': 'e2cb821b08bcd2e34dc866643069423d2552abfcc17834551953c91fc3bb7a17', 'results/a7_model_2_benchmark.csv': '680492e1c9d72c71e993a7d648e87bac46c0ee22156838686d1e7af50c2ba812', 'results/a7_model_2_scored.csv': '90d885c8c0ea4b71e160b9a20d01ac238da1564d359a61001ae596878c4b75e9', 'results/a7_model_3_benchmark.csv': 'e7c41a4ee85a442e771a14d2a3f38f08da258484c378102754a1146f7ec883b3', 'results/a7_model_3_scored.csv': '660ee746b9e9fd41738906ad0d2c82f14bd9ac1fbe9ecbadc5372420c1fa1b6f', 'results/a7_model_4_benchmark.csv': 'd2092a328664159e2d5e2192edc40f43be1aa3137c1ac1c947231b17bcdbc549', 'results/a7_model_4_scored.csv': '8c2d7c34da6ce00be1b5c6e47b1b45f3c2aab5f9ecc92897963afe2eaff99764', 'results/a7_model_5_benchmark.csv': '6d244931f184afe2fcbb3d0319ce5f6e5d5e0614807fb2381af1e175daf19575', 'results/a7_model_5_scored.csv': '899a67fed94c718515da4be07aadd7feae4cdb63cf45b137c3b52eea16a3aa8a', 'results/a7_stage1_all_benchmarks.csv': '8e16d5e898baa4eed59f674003a21e9524d026516c4503329f072a3fa4ba9ea0', 'results/a7_stage1_summary.csv': '3d45d52241ad60f6304db36f45fbe229f660e008fe4c9659f00b9fef9fd1bcf1', 'results/a7_stage1_local_cost.csv': '7e734f939fa09e8aac7e6e92bad99d2011fb30faf09b5aedf282658b4fe7f118', 'results/research_matrix.csv': '29194ca699d7c938d130f383fa792cb9c856712fabec713f622f295d2b6dcd48'}
PROMPT_SHA256 = '2c939da3d069af8ad7ae63ef59a1bf97f22387d199f45160fc57b38c64d775e1'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_inputs():
    notebook = json.loads((MODULE / "multi_model_system.ipynb").read_text())
    prompts = None
    for cell in notebook["cells"]:
        if cell["cell_type"] != "code":
            continue
        for node in ast.parse("".join(cell["source"])).body:
            if (isinstance(node, ast.Assign) and any(isinstance(x, ast.Name)
                    and x.id == "evaluation_prompts" for x in node.targets)):
                prompts = ast.literal_eval(node.value)
    if prompts is None:
        raise AssertionError("Prompt definitions missing")
    return notebook, pd.read_csv(RESULTS / "research_matrix.csv"), pd.DataFrame(
        prompts, columns=["Prompt ID", "Prompt Type", "Prompt"])


class Stage1Checks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nb, cls.matrix, cls.prompts = load_inputs()
        cls.models = shared.registry(cls.matrix)
        cls.pricing = json.loads((MODULE / "a7_api_pricing.json").read_text())
        cls.quotes = {int(k): v for k, v in cls.pricing["models"].items()}

    def test_unchanged_reviewed_files(self):
        for filename, expected in BASELINE.items():
            self.assertEqual(digest(MODULE / filename), expected, filename)

    def test_models_and_prompts(self):
        self.assertEqual(set(self.models), set(range(1, 16)))
        self.assertEqual(self.matrix["Category"].nunique(), 5)
        self.assertTrue(self.matrix["Category"].value_counts().eq(3).all())
        shared.validate_prompts(self.prompts)
        actual = hashlib.sha256(json.dumps(self.prompts.values.tolist()).encode()).hexdigest()
        self.assertEqual(actual, PROMPT_SHA256)

    def test_benchmark_integrity_scores_and_summary(self):
        frames = []
        for number in range(1, 6):
            raw = pd.read_csv(RESULTS / f"a7_model_{number}_benchmark.csv")
            scored = pd.read_csv(RESULTS / f"a7_model_{number}_scored.csv")
            shared.validate_records(scored, *self.models[number], self.prompts)
            self.assertEqual(len(scored), 25)
            score_cols = shared.SCORE_COLUMNS + ["Self-Evaluation Score (1-10)"]
            pd.testing.assert_frame_equal(raw.drop(columns=score_cols), scored.drop(columns=score_cols))
            for col in score_cols:
                self.assertTrue(scored[col].between(1, 10).all())
                self.assertTrue(scored[col].mod(1).eq(0).all())
            expected = scored[shared.SCORE_COLUMNS].mean(axis=1).map(lambda x: math.floor(x + .5))
            self.assertTrue(expected.eq(scored["Self-Evaluation Score (1-10)"]).all())
            frames.append(scored.assign(**{"Model No.": number}))
        combined = pd.concat(frames, ignore_index=True)
        saved = pd.read_csv(RESULTS / "a7_stage1_all_benchmarks.csv")
        self.assertEqual(len(combined), 125)
        pd.testing.assert_frame_equal(combined[saved.columns], saved)
        summary = combined.groupby(["Model No.", "Model", "Model Category"]).agg(
            Prompts=("Prompt ID", "count"), Average_Score=("Self-Evaluation Score (1-10)", "mean"),
            Average_Latency=("Latency", "mean"), Average_Tokens_Per_Sec=("Tokens/sec", "mean"),
            Token_Limit_Hits=("Reached Token Limit", "sum")).reset_index().round(2)
        pd.testing.assert_frame_equal(summary, pd.read_csv(RESULTS / "a7_stage1_summary.csv"))
        self.assertEqual(summary.Average_Score.tolist(), [2.76, 6.76, 7.96, 9.4, 9.6])

    def test_price_evidence_and_metadata(self):
        evidence = {(x["model"], x["provider"]): x for x in self.pricing["price_evidence"]}
        for quote in self.quotes.values():
            snapshot = evidence[(quote["model"], quote["provider"])]
            for field in ("input_usd_per_million", "output_usd_per_million"):
                self.assertEqual(quote[field], snapshot[field])
            self.assertTrue(quote["source_url"].startswith("https://huggingface.co/inference/models"))
            self.assertEqual(quote["checked_date"], "2026-10-21")
            self.assertTrue(quote["comparison_note"])
        self.assertEqual(set(self.quotes), set(range(1, 6)))

    def test_shared_costs_reproduce_all_rows(self):
        local, api = shared.calculate_costs(range(1, 6), self.matrix,
                                            {1: 60, 2: 45, 3: 30, 4: 20, 5: 12}, self.quotes)
        for frame, name in ((local, "local"), (api, "api")):
            self.assertEqual(len(frame), 30)
            self.assertFalse(frame.isna().any().any())
            self.assertTrue(frame.groupby("Daily Traffic Category").size().eq(5).all())
            pd.testing.assert_frame_equal(frame, pd.read_csv(RESULTS / f"a7_stage1_{name}_cost.csv"), check_dtype=False)
        for _, row in local.iterrows():
            self.assertEqual(row["Total Daily Token Load"], row["Daily Active Users"] * 500)
            count = math.ceil(row["Total Daily Token Load"] / (row["Cloud Throughput Assumption (tokens/sec)"] * 86400 * .7))
            self.assertEqual(row["Machines Needed"], count)
            self.assertEqual(row["Total Machine Cost"], shared.money(count * 1.006 * 720))
        for _, row in api.iterrows():
            users = shared.TRAFFIC[row["Daily Traffic Category"]]
            self.assertEqual(row["Total Daily Input Tokens"], users * 250)
            bill = (users * 250 * row["Input USD per 1M tokens"] + users * 500 * row["Output USD per 1M tokens"]) * 30 / 1e6
            self.assertAlmostEqual(row["Estimated API Cost"], bill, delta=.005001)
            gateways = max(1, math.ceil(users / (86400 * 100)))
            self.assertEqual(row["Machines Required (API infrastructure)"], gateways)
            self.assertEqual(row["API Gateway Cost"], gateways * 36)
            self.assertEqual(row["Total Cost"], shared.money(row["Estimated API Cost"] + row["API Gateway Cost"]))
        self.assertEqual(shared.money("0.525"), .53)

    def test_cost_validation(self):
        for kwargs in ({"utilization": 0}, {"utilization": 1.1}, {"gateway_rps": 0}, {"input_tokens": float("nan")}):
            with self.assertRaises(ValueError):
                shared.calculate_costs([1], self.matrix, {1: 60}, self.quotes, **kwargs)
        # The interface must extend beyond Stage 1 without modifying its rows.
        quotes = {6: self.quotes[1], 15: self.quotes[5]}
        local, api = shared.calculate_costs([6, 15], self.matrix, {6: 60, 15: 8}, quotes)
        self.assertEqual(len(local), 12)
        self.assertEqual(len(api), 12)

    def test_cpu_fp16_and_nf4_loading_configuration_without_weights(self):
        captured = {}
        class Tokenizer:
            @staticmethod
            def from_pretrained(model_id, **kwargs):
                captured["tokenizer"] = kwargs
                return object()
        class Model:
            @staticmethod
            def from_pretrained(model_id, **kwargs):
                captured["model"] = kwargs
                return types.SimpleNamespace(eval=lambda: None)
        class Quantization:
            def __init__(self, **kwargs):
                self.settings = kwargs
        fake_torch = types.SimpleNamespace(float16="FP16", float32="FP32", bfloat16="BF16",
                                            cuda=types.SimpleNamespace(is_available=lambda: True))
        fake_transformers = types.SimpleNamespace(AutoTokenizer=Tokenizer, AutoModelForCausalLM=Model,
                                                  BitsAndBytesConfig=Quantization)
        with patch.dict(sys.modules, {"torch": fake_torch, "transformers": fake_transformers}):
            shared.load_model("test/model", backend="cpu", precision="torch.bfloat16")
            self.assertEqual(captured["model"]["torch_dtype"], "BF16")
            shared.load_model("test/model", backend="cuda", precision="float16")
            self.assertEqual(captured["model"]["torch_dtype"], "FP16")
            self.assertEqual(captured["model"]["device_map"], {"": 0})
            shared.load_model("test/model", backend="cuda", precision="4-bit NF4")
            self.assertEqual(captured["model"]["quantization_config"].settings,
                             {"load_in_4bit": True, "bnb_4bit_quant_type": "nf4",
                              "bnb_4bit_compute_dtype": "FP16", "bnb_4bit_use_double_quant": True})
            self.assertFalse(captured["model"]["trust_remote_code"])
            self.assertEqual(captured["model"]["attn_implementation"], "eager")

    def test_gemma_message_wrapper(self):
        prompt = self.prompts.iloc[0]["Prompt"]
        messages = shared.prepare_messages("google/gemma-2-2b-it", prompt)
        self.assertEqual(messages, [{"role": "user", "content": shared.SYSTEM + "\n\n" + prompt}])
        for mid, _ in self.models.values():
            if "gemma-2" not in mid:
                self.assertEqual(shared.prepare_messages(mid, prompt)[1]["content"], prompt)

    def test_precision_aliases(self):
        for alias, canonical in [("torch.bfloat16", "bfloat16"), ("float16", "fp16"),
                                  ("4-bit NF4", "nf4"), ("torch.float32", "float32")]:
            self.assertEqual(shared.normalize_precision(alias), canonical)
        with self.assertRaises(ValueError):
            shared.normalize_precision("unknown")

    def test_default_inference_and_completed_history_are_safe(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(shared, "load_model", side_effect=AssertionError("Model loading forbidden")):
            self.assertEqual(shared.run_models(range(1, 16), self.matrix, self.prompts, folder), {})
            self.assertEqual(list(Path(folder).iterdir()), [])
            data = shared.run_models(range(1, 6), self.matrix, self.prompts, RESULTS,
                                     execute=True, backend="cpu", precision="float32")
            self.assertEqual(len(data), 5)  # No torch import needed for completed historical runs.

    def test_resume_rejects_invalid_or_incompatible_partial_runs(self):
        frame = pd.read_csv(RESULTS / "a7_model_1_benchmark.csv").head(1)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "a7_model_1_benchmark.csv"
            frame.to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "Partial resume"):
                shared.run_models([1], self.matrix, self.prompts, folder, execute=True)
            for column, value in [("Response", ""), ("Latency", -1), ("Tokens/sec", 99999),
                                  ("Generated Tokens", 300), ("Prompt", "changed")]:
                bad = frame.copy()
                bad.loc[bad.index[0], column] = value
                with self.assertRaises(ValueError):
                    shared.validate_records(bad, *self.models[1], self.prompts)
            first = shared.protocol_id(self.models[1][0], self.prompts, "cpu", "bfloat16")
            second = shared.protocol_id(self.models[1][0], self.prompts, "cuda", "fp16")
            self.assertNotEqual(first, second)

    def test_notebook_syntax_and_saved_outputs(self):
        for cell in self.nb["cells"]:
            if cell["cell_type"] == "code":
                ast.parse("".join(cell["source"]))
                self.assertIsNotNone(cell["execution_count"])
                self.assertTrue(cell["outputs"])
                self.assertFalse(any(o.get("output_type") == "error" for o in cell["outputs"]))
                self.assertNotIn(".to_csv(", "".join(cell["source"]))


def execute_notebook():
    """Execute real cells with in-process IPython (no kernel sockets required).

    Captures actual display/stream outputs, blocks inference imports and CSV
    writes, and returns the executed notebook without saving it.
    """
    import copy
    import contextlib
    from IPython.core.interactiveshell import InteractiveShell
    from IPython.utils.capture import capture_output
    class NoInferenceImports:
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in {"torch", "transformers", "bitsandbytes", "huggingface_hub"}:
                raise RuntimeError("Inference import forbidden during results-only execution")
    def no_csv_writes(*args, **kwargs):
        raise RuntimeError("Notebook CSV write forbidden")
    protected = {p: digest(p) for p in RESULTS.glob("*.csv")}
    original = json.loads((MODULE / "multi_model_system.ipynb").read_text())
    finder = NoInferenceImports()
    shell = InteractiveShell.instance()
    sys.meta_path.insert(0, finder)
    try:
        for cwd in (ROOT, MODULE):
            nb = copy.deepcopy(original)
            shell.reset(new_session=False)
            shell.execution_count = 1
            with contextlib.chdir(cwd), patch.object(pd.DataFrame, "to_csv", no_csv_writes):
                for index, cell in enumerate(nb["cells"], 1):
                    if cell["cell_type"] != "code":
                        continue
                    count = shell.execution_count
                    with capture_output() as captured:
                        result = shell.run_cell("".join(cell["source"]), store_history=True)
                    if result.error_before_exec or result.error_in_exec:
                        raise RuntimeError(f"Notebook cell {index} failed: {captured.stdout} {captured.stderr}") from (result.error_before_exec or result.error_in_exec)
                    outputs = []
                    if captured.stdout:
                        outputs.append({"output_type": "stream", "name": "stdout", "text": captured.stdout})
                    if captured.stderr:
                        outputs.append({"output_type": "stream", "name": "stderr", "text": captured.stderr})
                    for rich in captured.outputs:
                        outputs.append({"output_type": "display_data", "data": rich.data,
                                        "metadata": rich.metadata})
                    cell["execution_count"] = count
                    cell["outputs"] = outputs
            assert protected == {p: digest(p) for p in RESULTS.glob("*.csv")}
            print("PASS guarded in-process IPython execution:", cwd)
        return nb
    finally:
        sys.meta_path.remove(finder)


def check_live_prices():
    """Read official HTML price rows and live mappings; no authenticated inference."""
    import html
    import re
    import urllib.request
    from html.parser import HTMLParser
    class Rows(HTMLParser):
        def __init__(self):
            super().__init__(); self.rows = []; self.current = None
        def handle_starttag(self, tag, attrs):
            if tag == "tr": self.current = []
        def handle_data(self, data):
            if self.current is not None: self.current.append(data)
        def handle_endtag(self, tag):
            if tag == "tr" and self.current is not None:
                self.rows.append(" ".join(self.current)); self.current = None
    pricing = json.loads((MODULE / "a7_api_pricing.json").read_text())
    page = urllib.request.urlopen(pricing["verification_source"], timeout=30).read().decode()
    parser = Rows(); parser.feed(page)
    for item in pricing["price_evidence"]:
        short = item["model"].split("/")[-1]
        rows = [r for r in parser.rows if short in r and item["provider"] in r]
        assert rows, "Official price row unavailable: " + short
        expected = [item["input_usd_per_million"], item["output_usd_per_million"]]
        assert any([float(v) for v in re.findall(r"\$\s*([0-9.]+)", r)][:2] == expected for r in rows), short
        url = "https://huggingface.co/api/models/" + item["model"] + "?expand=inferenceProviderMapping"
        response = json.load(urllib.request.urlopen(url, timeout=30))
        assert response["inferenceProviderMapping"][item["provider"]]["status"] == "live"
        print("PASS official live model/provider and input/output prices:", item["model"], expected)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-notebook", action="store_true")
    parser.add_argument("--check-live-prices", action="store_true")
    args = parser.parse_args()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Stage1Checks))
    if not result.wasSuccessful():
        sys.exit(1)
    if args.execute_notebook:
        execute_notebook()
    if args.check_live_prices:
        check_live_prices()
