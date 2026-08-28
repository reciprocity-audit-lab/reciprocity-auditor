from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .errors import AuditorError
from .io_utils import (
    append_event,
    atomic_write_json,
    load_json,
    read_case,
    sensitive_categories,
    sha256_file,
    update_state,
    utc_now,
)


REVIEW_STATES = {"draft", "needs_revision", "reviewed"}
REVIEWER_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
REVIEW_SCOPE = "audit_report"
REVIEW_MEANING = "監査報告を人間が確認した状態であり、元の提案の採択・承認ではありません。"
DEFAULT_REPORT_FILE = "audit-report-ja.md"


def report_file_from_state(state: dict[str, Any]) -> str:
    value = state.get("report_file", DEFAULT_REPORT_FILE)
    if not isinstance(value, str) or not value or Path(value).name != value:
        raise AuditorError("invalid_report_file", "状態ファイルの監査報告書名が正しくありません。")
    return value


def review_integrity(case_dir: Path, state: dict[str, Any]) -> str:
    if state.get("review_status") != "reviewed":
        return "not_applicable"

    review_path = case_dir / "review.json"
    if not review_path.is_file() or review_path.is_symlink():
        return "review_record_missing"
    try:
        review = load_json(review_path)
    except AuditorError:
        return "review_record_invalid"
    if not isinstance(review, dict) or review.get("review_state") != "reviewed":
        return "review_record_invalid"
    if review.get("review_scope") not in (None, REVIEW_SCOPE):
        return "review_scope_invalid"

    recorded_hash = review.get("report_sha256")
    if recorded_hash is None:
        return "legacy_unbound"
    if not isinstance(recorded_hash, str) or re.fullmatch(r"[0-9a-f]{64}", recorded_hash) is None:
        return "review_record_invalid"

    report_file = review.get("report_file", report_file_from_state(state))
    if not isinstance(report_file, str) or not report_file or Path(report_file).name != report_file:
        return "review_record_invalid"
    report_path = case_dir / report_file
    if not report_path.is_file() or report_path.is_symlink():
        return "reviewed_report_missing"
    if sha256_file(report_path) != recorded_hash:
        return "reviewed_report_changed"
    return "valid"


def record_review(
    case_dir: Path,
    review_state: str,
    *,
    reviewer_label: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    if review_state not in REVIEW_STATES:
        raise AuditorError("invalid_review_state", "レビュー状態が許可されていません。")
    label = reviewer_label or "anonymous-reviewer"
    if REVIEWER_PATTERN.fullmatch(label) is None:
        raise AuditorError("invalid_reviewer_label", "担当者ラベルは匿名の英数字・ハイフン・下線にしてください。")
    if note is not None:
        if len(note) > 1_000:
            raise AuditorError("review_note_too_long", "レビューメモは1000文字以内にしてください。")
        if sensitive_categories(note):
            raise AuditorError("sensitive_review_note", "レビューメモに秘密情報または個人情報の可能性があります。")

    case, state = read_case(case_dir)
    report_file = report_file_from_state(state)
    report_path = case_dir / report_file
    if review_state == "reviewed":
        if state.get("validation_status") != "valid" or state.get("report_status") != "generated":
            raise AuditorError("review_prerequisite_missing", "reviewedにはJSON検証済みの生成済み報告書が必要です。")
        if not report_path.is_file() or report_path.is_symlink():
            raise AuditorError("reviewed_report_missing", "reviewedにはケース内の生成済み監査報告書が必要です。")

    review_record = {
        "format_version": "2",
        "case_id": case["case_id"],
        "proposal_sha256": case["proposal_sha256"],
        "review_state": review_state,
        "review_scope": REVIEW_SCOPE,
        "reviewer_label": label,
        "reviewed_at": utc_now(),
        "meaning": REVIEW_MEANING,
    }
    if report_path.is_file() and not report_path.is_symlink():
        review_record["report_file"] = report_file
        review_record["report_sha256"] = sha256_file(report_path)
    if note:
        review_record["note"] = note
    atomic_write_json(case_dir / "review.json", review_record)
    update_state(case_dir, state, review_status=review_state)
    append_event(
        case_dir,
        case_id=case["case_id"],
        proposal_sha256=case["proposal_sha256"],
        event="review",
        state=review_state,
    )
    return review_record


def case_status(case_dir: Path) -> dict[str, Any]:
    case, state = read_case(case_dir)
    analysis_file_exists = (case_dir / "analysis.json").is_file()
    integrity = review_integrity(case_dir, state)
    if state.get("review_status") == "reviewed" and integrity not in {"valid", "legacy_unbound"}:
        current = "人間確認記録不整合"
    elif state.get("review_status") == "reviewed":
        current = "reviewed"
    elif state.get("report_status") == "generated":
        current = "人間確認待ち"
    elif state.get("validation_status") == "valid":
        current = "JSON検証済み"
    elif state.get("validation_status") == "failed":
        current = "JSON検証失敗"
    elif analysis_file_exists:
        current = "AI回答あり・未検証"
    else:
        current = "AI回答待ち"

    return {
        "case_id": case["case_id"],
        "proposal_sha256": case["proposal_sha256"],
        "prepare": "済み" if state.get("prepare_status") == "prepared" else "未完了",
        "analysis": "あり" if analysis_file_exists else "待ち",
        "validation": state.get("validation_status", "unknown"),
        "report": state.get("report_status", "unknown"),
        "human_review": state.get("review_status", "draft"),
        "review_scope": REVIEW_SCOPE,
        "review_integrity": integrity,
        "current": current,
    }
