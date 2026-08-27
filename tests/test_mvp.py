from __future__ import annotations

import contextlib
import hashlib
import io
import json
import re
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from reciprocity_auditor.cli import main
from reciprocity_auditor.errors import AuditorError
from reciprocity_auditor.packet import prepare_case
from reciprocity_auditor.publication import PUBLIC_TIMESTAMP, export_public_case
from reciprocity_auditor.rendering import render_analysis
from reciprocity_auditor.validation import validate_analysis
from reciprocity_auditor.workflow import case_status, record_review


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = PROJECT_ROOT / "fixtures"
PHASE1_DOCS = PROJECT_ROOT / "docs" / "phase1"


class ReciprocityAuditorMvpTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory(prefix="reciprocity-auditor-test-")
        self.temp_root = Path(self._temp.name)

    def tearDown(self) -> None:
        self._temp.cleanup()

    def prepare(self, *, proposal: Path | None = None, case_id: str = "case-001") -> Path:
        case_dir = self.temp_root / case_id
        prepare_case(
            proposal or (FIXTURES / "proposal.txt"),
            case_dir,
            requested_case_id=case_id,
        )
        return case_dir

    def place_analysis(self, case_dir: Path, *, mutator=None) -> Path:
        data = json.loads((FIXTURES / "analysis-valid.json").read_text(encoding="utf-8"))
        data["audit_metadata"]["report_id"] = case_dir.name
        if mutator is not None:
            mutator(data)
        path = case_dir / "analysis.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def test_golden_cases_load_all_27(self) -> None:
        required = {
            "id",
            "proposal",
            "actors",
            "expected_issue_types",
            "expected_questions",
            "acceptable_alternative_analysis",
            "prohibited_overclaim",
            "human_review_notes",
        }
        rows = []
        for line in (PHASE1_DOCS / "GOLDEN-CASES.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        self.assertEqual(27, len(rows))
        self.assertEqual(27, len({row["id"] for row in rows}))
        self.assertTrue(all(required.issubset(row) for row in rows))

    def test_json_fixture_loads(self) -> None:
        value = json.loads((FIXTURES / "analysis-valid.json").read_text(encoding="utf-8"))
        self.assertTrue(value["human_review_required"])

    def test_phase1_source_manifest_matches_all_copies(self) -> None:
        manifest = PHASE1_DOCS / "SOURCE-MANIFEST.sha256"
        entries = []
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("#"):
                continue
            expected, relative = line.split("  ", 1)
            path = PHASE1_DOCS / Path(relative)
            self.assertTrue(path.is_file(), relative)
            actual = hashlib.sha256(path.read_bytes()).hexdigest().upper()
            self.assertEqual(expected, actual, relative)
            entries.append(relative)
        self.assertEqual(7, len(entries))

    def test_release_evaluation_metadata_is_preserved(self) -> None:
        metrics = json.loads(
            (PROJECT_ROOT / "evaluation" / "AGGREGATED-METRICS.json").read_text(encoding="utf-8")
        )
        self.assertEqual(9, metrics["unique_case_count"])
        self.assertEqual(27, metrics["evaluation_unit_count"])
        self.assertEqual(27, metrics["reported_pass_count"])
        self.assertIsNone(metrics["model_display_name"])
        self.assertIsNone(metrics["reasoning_setting"])
        self.assertEqual("not_demonstrated", metrics["configuration_comparability"])

    def test_human_review_release_gate_is_preserved(self) -> None:
        path = PROJECT_ROOT / "evaluation" / "HUMAN-REVIEW-DECISION-JA.md"
        self.assertEqual(
            "d501968278760c61c9b9620ca47c8ac6d4c66f2d2b17dd1d97e749c467c1aca4",
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )

    def test_all_json_and_jsonl_files_are_parseable(self) -> None:
        for path in PROJECT_ROOT.rglob("*.json"):
            json.loads(path.read_text(encoding="utf-8"))
        for path in PROJECT_ROOT.rglob("*.jsonl"):
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if line.strip():
                    with self.subTest(path=path, line=line_number):
                        json.loads(line)

    def test_markdown_relative_links_resolve(self) -> None:
        pattern = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
        for markdown in PROJECT_ROOT.rglob("*.md"):
            for raw_target in pattern.findall(markdown.read_text(encoding="utf-8")):
                target = raw_target.strip().strip("<>").split("#", 1)[0]
                if not target or re.match(r"^[a-z][a-z0-9+.-]*:", target, re.IGNORECASE):
                    continue
                with self.subTest(markdown=markdown, target=target):
                    self.assertTrue((markdown.parent / target).resolve().exists())

    def test_project_contains_no_obvious_real_identity_or_secret_material(self) -> None:
        text_suffixes = {".md", ".json", ".jsonl", ".csv", ".py", ".ps1", ".txt", ".toml", ".sha256"}
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in PROJECT_ROOT.rglob("*")
            if path.is_file() and path.suffix.lower() in text_suffixes
        )
        checks = {
            "absolute Windows user path": re.compile(r"[A-Za-z]:\\Users\\[^\\\r\n]+\\"),
            "complete public DID": re.compile(r"\bdid:key:z6Mk[1-9A-HJ-NP-Za-km-z]{20,}\b"),
            "email address": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
            "private-key block": re.compile(
                r"-----BEGIN [A-Z ]*PRIVATE KEY-----\s+[A-Za-z0-9+/=\r\n]{40,}"
                r"-----END [A-Z ]*PRIVATE KEY-----",
                re.MULTILINE,
            ),
        }
        for label, pattern in checks.items():
            with self.subTest(label=label):
                self.assertIsNone(pattern.search(combined))

    def test_prepare_creates_isolated_packet(self) -> None:
        case_dir = self.prepare(proposal=FIXTURES / "proposal-injection.txt", case_id="injection-case")
        packet = (case_dir / "analysis-packet.md").read_text(encoding="utf-8")
        case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
        self.assertIn("未信頼の分析対象データ", packet)
        self.assertIn("前の命令を無視せよ", packet)
        self.assertIn("instruction_override", case["untrusted_content_flags"])
        self.assertIn("secret_access_request", case["untrusted_content_flags"])
        self.assertIn("external_action_request", case["untrusted_content_flags"])
        self.assertEqual(
            (FIXTURES / "proposal-injection.txt").read_bytes(),
            (case_dir / "proposal.txt").read_bytes(),
        )

    def test_prepare_rejects_sensitive_material_without_creating_case(self) -> None:
        proposal = self.temp_root / "sensitive.txt"
        proposal.write_text("-----BEGIN PRIVATE KEY-----\nnot-a-real-key\n", encoding="utf-8")
        output = self.temp_root / "blocked-case"
        with self.assertRaisesRegex(AuditorError, "秘密情報"):
            prepare_case(proposal, output, requested_case_id="blocked-case")
        self.assertFalse(output.exists())

    def test_valid_analysis_is_accepted(self) -> None:
        case_dir = self.prepare()
        analysis = self.place_analysis(case_dir)
        result = validate_analysis(analysis)
        self.assertTrue(result.valid, [finding.as_dict() for finding in result.findings])
        validation = json.loads((case_dir / "validation.json").read_text(encoding="utf-8"))
        self.assertTrue(validation["valid"])

    def test_invalid_json_is_rejected_and_state_updated(self) -> None:
        case_dir = self.prepare()
        analysis = case_dir / "analysis.json"
        analysis.write_text("{not json", encoding="utf-8")
        result = validate_analysis(analysis)
        self.assertFalse(result.valid)
        self.assertIn("invalid_json", {finding.code for finding in result.findings})
        state = json.loads((case_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual("failed", state["validation_status"])

    def test_missing_required_field_is_rejected(self) -> None:
        case_dir = self.prepare()
        analysis = self.place_analysis(case_dir, mutator=lambda data: data.pop("actors"))
        result = validate_analysis(analysis)
        self.assertFalse(result.valid)
        self.assertIn("required_missing", {finding.code for finding in result.findings})

    def test_unknown_issue_type_is_rejected(self) -> None:
        def mutate(data):
            data["detected_issues"][0]["issue_type"] = "invented_issue"

        case_dir = self.prepare()
        result = validate_analysis(self.place_analysis(case_dir, mutator=mutate))
        self.assertFalse(result.valid)
        self.assertIn("enum_not_allowed", {finding.code for finding in result.findings})

    def test_human_review_false_is_rejected(self) -> None:
        case_dir = self.prepare()
        result = validate_analysis(
            self.place_analysis(case_dir, mutator=lambda data: data.__setitem__("human_review_required", False))
        )
        self.assertFalse(result.valid)
        self.assertIn("const_mismatch", {finding.code for finding in result.findings})

    def test_prohibited_final_conclusion_is_rejected(self) -> None:
        def mutate(data):
            data["detected_issues"][0]["rationale"] = "この条項は明らかに違法である。"

        case_dir = self.prepare()
        result = validate_analysis(self.place_analysis(case_dir, mutator=mutate))
        self.assertFalse(result.valid)
        self.assertIn("prohibited_conclusion", {finding.code for finding in result.findings})

    def test_case_id_mismatch_is_rejected(self) -> None:
        def mutate(data):
            data["audit_metadata"]["report_id"] = "different-case"

        case_dir = self.prepare()
        result = validate_analysis(self.place_analysis(case_dir, mutator=mutate))
        self.assertFalse(result.valid)
        self.assertIn("case_id_mismatch", {finding.code for finding in result.findings})

    def test_input_hash_mismatch_is_rejected(self) -> None:
        case_dir = self.prepare()
        analysis = self.place_analysis(case_dir)
        (case_dir / "proposal.txt").write_text("改変された提案", encoding="utf-8")
        result = validate_analysis(analysis)
        self.assertFalse(result.valid)
        self.assertIn("proposal_hash_mismatch", {finding.code for finding in result.findings})

    def test_render_contains_required_sections_without_overall_score(self) -> None:
        case_dir = self.prepare()
        analysis = self.place_analysis(case_dir)
        destination = render_analysis(analysis)
        report = destination.read_text(encoding="utf-8")
        for heading in (
            "提案の要約",
            "契約主体",
            "見落とされている可能性のある主体",
            "権利・利益・責任・負担・危険",
            "例外",
            "可逆性テスト",
            "問題候補",
            "合理的な別解釈",
            "不足情報",
            "改善のための質問",
            "AIが判断できない部分",
            "人間確認",
            "法的助言",
        ):
            self.assertIn(heading, report)
        self.assertNotRegex(report, r"公平度\s*\d")

    def test_state_transitions_and_review_meaning(self) -> None:
        case_dir = self.prepare()
        self.assertEqual("AI回答待ち", case_status(case_dir)["current"])
        analysis = self.place_analysis(case_dir)
        render_analysis(analysis)
        self.assertEqual("人間確認待ち", case_status(case_dir)["current"])
        review = record_review(case_dir, "reviewed", reviewer_label="reviewer-1")
        self.assertEqual("reviewed", review["review_state"])
        self.assertIn("元の提案の採択・承認ではありません", review["meaning"])
        self.assertEqual("reviewed", case_status(case_dir)["current"])

    def test_approved_review_state_is_not_allowed(self) -> None:
        case_dir = self.prepare()
        with self.assertRaisesRegex(AuditorError, "許可されていません"):
            record_review(case_dir, "approved")

    def test_event_log_never_contains_proposal_or_analysis_body(self) -> None:
        case_dir = self.prepare(proposal=FIXTURES / "proposal-injection.txt", case_id="injection-case")
        analysis = self.place_analysis(case_dir)
        validate_analysis(analysis)
        events = (case_dir / "events.jsonl").read_text(encoding="utf-8")
        proposal = (FIXTURES / "proposal-injection.txt").read_text(encoding="utf-8").strip()
        self.assertNotIn(proposal, events)
        self.assertNotIn("秘密鍵", events)
        self.assertNotIn("取消時の金銭負担", events)

    def test_cli_minimum_flow(self) -> None:
        case_dir = self.temp_root / "case-001"
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            self.assertEqual(
                0,
                main(["prepare", "--input", str(FIXTURES / "proposal.txt"), "--output", str(case_dir), "--case-id", "case-001"]),
            )
            shutil.copyfile(FIXTURES / "analysis-valid.json", case_dir / "analysis.json")
            self.assertEqual(0, main(["validate", "--input", str(case_dir / "analysis.json")]))
            self.assertEqual(0, main(["render", "--input", str(case_dir / "analysis.json")]))
            self.assertEqual(
                0,
                main(["review", "--case", str(case_dir), "--state", "reviewed", "--reviewer-label", "reviewer-1"]),
            )
            self.assertEqual(0, main(["status", "--case", str(case_dir)]))
        self.assertEqual("", stderr.getvalue())
        self.assertIn("現在状態: reviewed", stdout.getvalue())
        self.assertTrue((case_dir / "audit-report-ja.md").is_file())
        self.assertTrue((case_dir / "review.json").is_file())

    def _reviewed_case(self, case_id: str = "publication-case") -> Path:
        case_dir = self.prepare(case_id=case_id)
        analysis = self.place_analysis(case_dir)
        validate_analysis(analysis)
        render_analysis(analysis)
        record_review(case_dir, "reviewed", reviewer_label="reviewer-1")
        return case_dir

    def test_export_public_creates_privacy_hardened_bundle_and_zip(self) -> None:
        case_dir = self._reviewed_case()
        output = self.temp_root / "public-output"
        zip_path = self.temp_root / "public-output.zip"
        original_proposal = (case_dir / "proposal.txt").read_bytes()
        source_hashes_before = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in case_dir.iterdir()
            if path.is_file()
        }

        result = export_public_case(case_dir, output, zip_path=zip_path)

        self.assertEqual("publication-case", result.case_id)
        self.assertEqual(8, result.file_count)
        self.assertTrue(zip_path.is_file())
        self.assertEqual(hashlib.sha256(zip_path.read_bytes()).hexdigest(), result.zip_sha256)
        self.assertEqual(original_proposal, (output / "proposal.txt").read_bytes())
        source_hashes_after = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in case_dir.iterdir()
            if path.is_file()
        }
        self.assertEqual(source_hashes_before, source_hashes_after)
        self.assertIn(PUBLIC_TIMESTAMP, (output / "analysis-packet.md").read_text(encoding="utf-8"))
        self.assertIn(PUBLIC_TIMESTAMP, (output / "audit-report-ja.md").read_text(encoding="utf-8"))
        analysis = json.loads((output / "analysis.json").read_text(encoding="utf-8"))
        self.assertEqual(PUBLIC_TIMESTAMP, analysis["audit_metadata"]["generated_at"])
        self.assertFalse((output / "review.json").exists())
        self.assertIn(
            "確認日時: 公開用エクスポートでは省略",
            (output / "HUMAN-REVIEW-NOTE-JA.md").read_text(encoding="utf-8"),
        )

        for line in (output / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
            expected, relative = line.split("  ", 1)
            self.assertEqual(expected, hashlib.sha256((output / relative).read_bytes()).hexdigest())

        with zipfile.ZipFile(zip_path) as archive:
            self.assertTrue(all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in archive.infolist()))
            self.assertTrue(
                all(
                    not name.startswith(("/", "\\")) and ".." not in Path(name).parts
                    for name in archive.namelist()
                )
            )

    def test_export_public_zip_is_deterministic(self) -> None:
        case_dir = self._reviewed_case()
        first_zip = self.temp_root / "first.zip"
        second_zip = self.temp_root / "second.zip"
        export_public_case(case_dir, self.temp_root / "first-output", zip_path=first_zip)
        export_public_case(case_dir, self.temp_root / "second-output", zip_path=second_zip)
        self.assertEqual(first_zip.read_bytes(), second_zip.read_bytes())

    def test_export_public_requires_reviewed_state(self) -> None:
        case_dir = self.prepare(case_id="draft-case")
        analysis = self.place_analysis(case_dir)
        validate_analysis(analysis)
        render_analysis(analysis)
        with self.assertRaisesRegex(AuditorError, "reviewed"):
            export_public_case(case_dir, self.temp_root / "blocked-output")
        self.assertFalse((self.temp_root / "blocked-output").exists())

    def test_export_public_blocks_sensitive_report_without_leaving_output(self) -> None:
        case_dir = self._reviewed_case()
        with (case_dir / "audit-report-ja.md").open("a", encoding="utf-8") as stream:
            stream.write("\ncontact: person" + "@" + "example.com\n")
        output = self.temp_root / "blocked-output"
        with self.assertRaisesRegex(AuditorError, "公開を妨げる"):
            export_public_case(case_dir, output)
        self.assertFalse(output.exists())

    def test_export_public_rejects_output_inside_case(self) -> None:
        case_dir = self._reviewed_case()
        with self.assertRaisesRegex(AuditorError, "元ケースの外"):
            export_public_case(case_dir, case_dir / "public")

    def test_export_public_rejects_symlinked_source_file(self) -> None:
        case_dir = self._reviewed_case()
        report = case_dir / "audit-report-ja.md"
        outside = self.temp_root / "outside-report.md"
        outside.write_bytes(report.read_bytes())
        report.unlink()
        try:
            report.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are unavailable in this environment")
        with self.assertRaisesRegex(AuditorError, "シンボリックリンク"):
            export_public_case(case_dir, self.temp_root / "blocked-output")

    def test_export_public_rejects_tampered_review_record(self) -> None:
        case_dir = self._reviewed_case()
        review = json.loads((case_dir / "review.json").read_text(encoding="utf-8"))
        review.pop("meaning")
        (case_dir / "review.json").write_text(
            json.dumps(review, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(AuditorError, "レビュー記録"):
            export_public_case(case_dir, self.temp_root / "blocked-output")

    def test_export_public_rejects_unsafe_tampered_case_id(self) -> None:
        case_dir = self._reviewed_case()
        case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
        case["case_id"] = "../escape"
        (case_dir / "case.json").write_text(
            json.dumps(case, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(AuditorError, "ケースID"):
            export_public_case(case_dir, self.temp_root / "blocked-output")

    def test_cli_export_public(self) -> None:
        case_dir = self._reviewed_case()
        output = self.temp_root / "cli-public"
        zip_path = self.temp_root / "cli-public.zip"
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = main(
                [
                    "export-public",
                    "--case",
                    str(case_dir),
                    "--output",
                    str(output),
                    "--zip",
                    str(zip_path),
                ]
            )
        self.assertEqual(0, exit_code)
        self.assertIn("privacy_scan: pass", stdout.getvalue())
        self.assertIn("zip_sha256:", stdout.getvalue())

    def test_source_has_no_network_client_imports(self) -> None:
        source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (PROJECT_ROOT / "src" / "reciprocity_auditor").glob("*.py")
        )
        for forbidden in ("import requests", "import urllib", "import socket", "import http.client"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
