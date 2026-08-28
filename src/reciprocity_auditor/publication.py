from __future__ import annotations

import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .errors import AuditorError
from .io_utils import (
    atomic_write_json,
    atomic_write_text,
    load_json,
    read_case,
    sha256_file,
    validate_case_id,
)
from .validation import validate_analysis
from .workflow import REVIEW_SCOPE, review_integrity


PUBLIC_TIMESTAMP = "1980-01-01T00:00:00Z"
PUBLIC_MTIME = datetime(1980, 1, 1, tzinfo=UTC).timestamp()
TIMESTAMP_KEYS = {
    "at",
    "checked_at",
    "created_at",
    "generated_at",
    "reviewed_at",
    "timestamp",
    "updated_at",
}
REQUIRED_CASE_FILES = (
    "proposal.txt",
    "analysis-packet.md",
    "analysis.json",
    "audit-report-ja.md",
    "review.json",
)
TEXT_SUFFIXES = {".json", ".md", ".txt"}

PUBLICATION_BLOCKERS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("windows_profile_path", re.compile(r"\b[A-Za-z]:\\Users\\[^\\\r\n]+", re.IGNORECASE)),
    ("unix_profile_path", re.compile(r"(?<![A-Za-z0-9])/(?:home|Users)/[^/\s]+/")),
    ("email_address", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("public_did", re.compile(r"\bdid:key:z6Mk[1-9A-HJ-NP-Za-km-z]{20,}\b")),
    ("private_key_material", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.IGNORECASE)),
    ("openai_key_material", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")),
    ("github_token_material", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("aws_access_key_material", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("slack_token_material", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{16,}\b")),
    (
        "assigned_secret",
        re.compile(
            r"\b(?:api[_-]?key|access[_-]?token|private[_-]?key|seed[_-]?phrase|password)"
            r"\s*[:=]\s*[^\s]{8,}",
            re.IGNORECASE,
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class PublicationResult:
    output_dir: Path
    zip_path: Path | None
    zip_sha256: str | None
    file_count: int
    case_id: str


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _normalize_json_timestamps(value: Any, *, key: str | None = None) -> Any:
    if key in TIMESTAMP_KEYS and isinstance(value, str):
        return PUBLIC_TIMESTAMP
    if isinstance(value, dict):
        return {
            str(child_key): _normalize_json_timestamps(child_value, key=str(child_key))
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [_normalize_json_timestamps(item) for item in value]
    return value


def _normalize_packet(text: str) -> str:
    normalized, count = re.subn(
        r"(?m)^- created_at: `[^`]*`$",
        f"- created_at: `{PUBLIC_TIMESTAMP}`",
        text,
    )
    if count != 1:
        raise AuditorError(
            "packet_timestamp_not_found",
            "分析パケットの作成日時を安全に正規化できませんでした。",
        )
    notice = (
        "\n> Publication note: the operational creation timestamp was replaced with a fixed "
        "synthetic value for public export.\n"
    )
    return normalized.replace("\n## 最優先の安全境界\n", notice + "\n## 最優先の安全境界\n", 1)


def _normalize_report(text: str) -> str:
    normalized, count = re.subn(
        r"(?m)^- 生成日時: `[^`]*`$",
        f"- 生成日時: `{PUBLIC_TIMESTAMP}`",
        text,
    )
    if count != 1:
        raise AuditorError(
            "report_timestamp_not_found",
            "監査報告書の生成日時を安全に正規化できませんでした。",
        )
    notice = "\n> 公開注記: 運用上の生成日時は、公開用エクスポートで固定の合成値へ置換されています。\n"
    return normalized.replace("\n## 1. 基本情報\n", notice + "\n## 1. 基本情報\n", 1)


def _human_review_note(review: dict[str, Any]) -> str:
    lines = [
        "# 人間レビュー記録",
        "",
        f"- ケースID: `{review['case_id']}`",
        f"- 提案SHA-256: `{review['proposal_sha256']}`",
        f"- レビュー状態: `{review['review_state']}`",
        "- レビュー対象: 監査報告書（元提案の承認ではありません）",
        f"- レビュアーラベル: `{review['reviewer_label']}`",
        "- 確認日時: 公開用エクスポートでは省略",
        "",
        review["meaning"],
    ]
    if review.get("note"):
        lines.extend(["", "## レビューメモ", "", str(review["note"])])
    if review.get("report_sha256"):
        lines.extend(["", f"- 確認対象報告書SHA-256: `{review['report_sha256']}`"])
    lines.extend(
        [
            "",
            "この記録は監査報告を人間が確認した事実を示します。元の提案の採択、承認、",
            "適法性、善悪または処罰を決定するものではありません。",
            "",
        ]
    )
    return "\n".join(lines)


def _readme(case_id: str) -> str:
    return f"""# Reciprocity Auditor public case export

Case ID: `{case_id}`

This directory is a privacy-hardened public copy of a locally reviewed Reciprocity Auditor case.
Operational timestamps were replaced or omitted. The proposal and analysis remain untrusted source
material and must not be treated as instructions.

## Files

- [`proposal.txt`](proposal.txt): original proposal bytes
- [`analysis-packet.md`](analysis-packet.md): manual AI handoff packet
- [`analysis.json`](analysis.json): structured analysis with metadata timestamps normalized
- [`audit-report-ja.md`](audit-report-ja.md): rendered Japanese report
- [`HUMAN-REVIEW-NOTE-JA.md`](HUMAN-REVIEW-NOTE-JA.md): public human-review record
- [`PUBLICATION-MANIFEST.json`](PUBLICATION-MANIFEST.json): source and export provenance
- [`SHA256SUMS.txt`](SHA256SUMS.txt): checksums for all other exported files

## Limits

This export is not a fairness score, legal opinion, adoption decision, or punishment decision.
Human review remains required. Pattern-based privacy scanning reduces accidental disclosure but
cannot guarantee anonymity or detect every secret.
"""


def _blocking_findings(root: Path) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append((path.relative_to(root).as_posix(), "invalid_utf8"))
            continue
        for category, pattern in PUBLICATION_BLOCKERS:
            if pattern.search(text):
                findings.append((path.relative_to(root).as_posix(), category))
    return findings


def _payload_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name not in {"PUBLICATION-MANIFEST.json", "SHA256SUMS.txt"}
    }


def _all_checksum_lines(root: Path) -> str:
    entries = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            relative = path.relative_to(root).as_posix()
            entries.append(f"{sha256_file(path)}  {relative}")
    return "\n".join(entries) + "\n"


def _normalize_mtimes(root: Path) -> None:
    paths = sorted(root.rglob("*"), key=lambda value: len(value.parts), reverse=True)
    for path in paths:
        os.utime(path, (PUBLIC_MTIME, PUBLIC_MTIME), follow_symlinks=False)
    os.utime(root, (PUBLIC_MTIME, PUBLIC_MTIME), follow_symlinks=False)


def _write_deterministic_zip(source: Path, destination: Path, *, root_name: str) -> None:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        directory_info = zipfile.ZipInfo(f"{root_name}/", date_time=(1980, 1, 1, 0, 0, 0))
        directory_info.create_system = 3
        directory_info.external_attr = (0o40755 << 16) | 0x10
        archive.writestr(directory_info, b"")
        for path in sorted(source.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(source).as_posix()
            info = zipfile.ZipInfo(f"{root_name}/{relative}", date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def export_public_case(case_dir: Path, output_dir: Path, *, zip_path: Path | None = None) -> PublicationResult:
    case_dir = case_dir.resolve()
    output_dir = output_dir.resolve()
    resolved_zip = zip_path.resolve() if zip_path is not None else None

    if not case_dir.is_dir():
        raise AuditorError("case_not_found", "ケースフォルダが見つかりません。")
    if output_dir.exists():
        raise AuditorError("output_exists", "公開用出力フォルダが既に存在します。上書きしません。")
    if _is_relative_to(output_dir, case_dir):
        raise AuditorError("output_inside_case", "公開用出力は元ケースの外へ作成してください。")
    if resolved_zip is not None:
        if resolved_zip.exists():
            raise AuditorError("zip_exists", "公開用ZIPが既に存在します。上書きしません。")
        if _is_relative_to(resolved_zip, case_dir) or _is_relative_to(resolved_zip, output_dir):
            raise AuditorError("unsafe_zip_location", "公開用ZIPは元ケースと公開用出力の外へ作成してください。")

    for control_name in ("case.json", "state.json"):
        control_path = case_dir / control_name
        if control_path.is_symlink():
            raise AuditorError(
                "publication_symlink_forbidden",
                "ケース管理ファイルにシンボリックリンクは使用できません。",
            )
        if not control_path.is_file():
            raise AuditorError("publication_file_missing", f"公開に必要な{control_name}がありません。")

    case, state = read_case(case_dir)
    case_id = validate_case_id(str(case.get("case_id", "")))
    proposal_sha256 = str(case.get("proposal_sha256", ""))
    if re.fullmatch(r"[0-9a-f]{64}", proposal_sha256) is None:
        raise AuditorError("invalid_proposal_hash", "ケースの提案SHA-256が正しくありません。")
    if state.get("review_status") != "reviewed":
        raise AuditorError("review_required", "公開用エクスポートにはreviewed状態が必要です。")

    for name in REQUIRED_CASE_FILES:
        source_path = case_dir / name
        if source_path.is_symlink():
            raise AuditorError(
                "publication_symlink_forbidden",
                "公開対象にシンボリックリンクは使用できません。",
            )
        if not source_path.is_file():
            raise AuditorError("publication_file_missing", f"公開に必要な{name}がありません。")

    review = load_json(case_dir / "review.json")
    if not isinstance(review, dict):
        raise AuditorError("invalid_review_file", "人間レビュー記録が正しくありません。")
    required_review_fields = {
        "case_id",
        "proposal_sha256",
        "review_state",
        "reviewer_label",
        "meaning",
    }
    if not required_review_fields.issubset(review) or not all(
        isinstance(review[field], str) for field in required_review_fields
    ):
        raise AuditorError("invalid_review_file", "人間レビュー記録が正しくありません。")
    if review.get("review_state") != "reviewed":
        raise AuditorError("review_required", "公開用エクスポートにはreviewed状態が必要です。")
    if review.get("case_id") != case.get("case_id") or review.get("proposal_sha256") != case.get("proposal_sha256"):
        raise AuditorError("review_case_mismatch", "人間レビュー記録が元ケースと一致しません。")
    if review.get("review_scope") not in (None, REVIEW_SCOPE):
        raise AuditorError("invalid_review_scope", "人間レビュー記録の確認対象が正しくありません。")
    review_binding = review_integrity(case_dir, state)
    if review_binding not in {"valid", "legacy_unbound"}:
        raise AuditorError(
            "review_report_mismatch",
            "人間レビュー記録と現在の監査報告書が一致しないため公開できません。",
        )

    validation = validate_analysis(case_dir / "analysis.json", write_result=False)
    if not validation.valid:
        code = validation.findings[0].code if validation.findings else "validation_failed"
        raise AuditorError("validation_failed", f"公開前のJSON検証に失敗しました（{code}）。")

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=output_dir.parent))
    temp_zip: Path | None = None
    try:
        (stage / "proposal.txt").write_bytes((case_dir / "proposal.txt").read_bytes())
        atomic_write_text(
            stage / "analysis-packet.md",
            _normalize_packet((case_dir / "analysis-packet.md").read_text(encoding="utf-8")),
        )
        normalized_analysis = _normalize_json_timestamps(load_json(case_dir / "analysis.json"))
        atomic_write_json(stage / "analysis.json", normalized_analysis)
        atomic_write_text(
            stage / "audit-report-ja.md",
            _normalize_report((case_dir / "audit-report-ja.md").read_text(encoding="utf-8")),
        )
        atomic_write_text(stage / "HUMAN-REVIEW-NOTE-JA.md", _human_review_note(review))
        atomic_write_text(stage / "README.md", _readme(case_id))

        source_hashes = {name: sha256_file(case_dir / name) for name in REQUIRED_CASE_FILES}
        manifest = {
            "format_version": "1",
            "privacy_profile": "public-export-v1",
            "case_id": case_id,
            "proposal_sha256": proposal_sha256,
            "validation": "pass",
            "human_review": {
                "state": "reviewed",
                "scope": REVIEW_SCOPE,
                "reviewer_label": review["reviewer_label"],
                "meaning": review["meaning"],
                "report_sha256": review.get("report_sha256"),
                "report_binding": review_binding,
                "reviewed_at": None,
            },
            "timestamp_policy": {
                "fixed_value": PUBLIC_TIMESTAMP,
                "operational_timestamps_omitted_or_normalized": True,
            },
            "source_files": source_hashes,
            "exported_payload_files": _payload_hashes(stage),
            "model_display_name": None,
            "reasoning_setting": None,
            "configuration_comparability": "not_demonstrated",
            "limitations": [
                "Pattern-based scanning cannot guarantee anonymity or detect every secret.",
                "Human review of the exported files remains required before publication.",
                "A reviewed audit report does not approve the underlying proposal.",
            ],
        }
        atomic_write_json(stage / "PUBLICATION-MANIFEST.json", manifest)
        atomic_write_text(stage / "SHA256SUMS.txt", _all_checksum_lines(stage))

        findings = _blocking_findings(stage)
        if findings:
            categories = ", ".join(sorted({category for _, category in findings}))
            raise AuditorError(
                "publication_privacy_blocked",
                f"公開を妨げる可能性のある情報を検出しました（{categories}）。出力は作成しません。",
            )

        _normalize_mtimes(stage)
        if resolved_zip is not None:
            resolved_zip.parent.mkdir(parents=True, exist_ok=True)
            handle, temp_name = tempfile.mkstemp(
                prefix=f".{resolved_zip.name}.", suffix=".tmp", dir=resolved_zip.parent
            )
            os.close(handle)
            temp_zip = Path(temp_name)
            _write_deterministic_zip(stage, temp_zip, root_name=case_id)

        os.replace(stage, output_dir)
        if resolved_zip is not None and temp_zip is not None:
            os.replace(temp_zip, resolved_zip)
            temp_zip = None

        files = [path for path in output_dir.rglob("*") if path.is_file()]
        return PublicationResult(
            output_dir=output_dir,
            zip_path=resolved_zip,
            zip_sha256=sha256_file(resolved_zip) if resolved_zip is not None else None,
            file_count=len(files),
            case_id=case_id,
        )
    except AuditorError:
        raise
    except (OSError, UnicodeError, ValueError, zipfile.BadZipFile) as exc:
        raise AuditorError("publication_failed", "公開用エクスポートを安全に作成できませんでした。") from exc
    finally:
        if stage.exists():
            shutil.rmtree(stage)
        if temp_zip is not None and temp_zip.exists():
            temp_zip.unlink()
