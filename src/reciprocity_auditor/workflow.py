from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .errors import AuditorError
from .io_utils import (
    append_event,
    atomic_write_json,
    read_case,
    sensitive_categories,
    update_state,
    utc_now,
)


REVIEW_STATES = {"draft", "needs_revision", "reviewed"}
REVIEWER_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


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
    if review_state == "reviewed":
        if state.get("validation_status") != "valid" or state.get("report_status") != "generated":
            raise AuditorError("review_prerequisite_missing", "reviewedにはJSON検証済みの生成済み報告書が必要です。")

    review_record = {
        "case_id": case["case_id"],
        "proposal_sha256": case["proposal_sha256"],
        "review_state": review_state,
        "reviewer_label": label,
        "reviewed_at": utc_now(),
        "meaning": "監査報告を人間が確認した状態であり、元の提案の採択・承認ではありません。",
    }
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
    if state.get("review_status") == "reviewed":
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
        "current": current,
    }
