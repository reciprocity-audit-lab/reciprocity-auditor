from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .errors import AuditorError
from .io_utils import (
    atomic_write_json,
    load_json,
    read_case,
    sensitive_categories,
    sha256_file,
    utc_now,
    validate_case_id,
)
from .validation import validate_analysis


CONFIGURATION_EVIDENCE_SOURCES = {
    "model_ui",
    "run_manifest",
    "operator_observation",
    "unavailable",
}
REVIEW_STATES = {"needs_revision", "reviewed"}
INDEPENDENCE_STATUSES = {"independent", "not_independent", "unknown"}
LABEL_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
VALUE_PATTERN = re.compile(r"^[^\r\n]{1,120}$")
REVIEW_MEANING = (
    "3視点の構造比較を人間が確認した記録であり、元提案、各監査報告、"
    "公平性、適法性、採否、執行、処罰の承認または最終判断ではありません。"
)


def _explicit_value(value: str | None, label: str) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if VALUE_PATTERN.fullmatch(normalized) is None:
        raise AuditorError("invalid_configuration_value", f"{label}は改行なし120文字以内にしてください。")
    if sensitive_categories(normalized):
        raise AuditorError("sensitive_configuration_value", f"{label}に秘密情報または個人情報の可能性があります。")
    return normalized


def record_run_configuration(
    case_dir: Path,
    *,
    evidence_source: str,
    model_display_name: str | None = None,
    reasoning_setting: str | None = None,
) -> dict[str, Any]:
    destination = case_dir / "run-configuration.json"
    if destination.exists():
        raise AuditorError("configuration_record_exists", "実行構成記録が既にあります。上書きしません。")
    if evidence_source not in CONFIGURATION_EVIDENCE_SOURCES:
        raise AuditorError("invalid_evidence_source", "実行構成の証拠元が許可されていません。")

    model = _explicit_value(model_display_name, "モデル表示名")
    reasoning = _explicit_value(reasoning_setting, "推論設定")
    if evidence_source == "unavailable":
        if model is not None or reasoning is not None:
            raise AuditorError("unavailable_with_values", "unavailableではモデル名や推論設定を記録できません。")
    elif model is None and reasoning is None:
        raise AuditorError("explicit_value_required", "明示的な証拠元にはモデル表示名または推論設定が必要です。")

    case, _ = read_case(case_dir)
    validate_case_id(str(case.get("case_id", "")))
    analysis_path = case_dir / "analysis.json"
    result = validate_analysis(analysis_path, write_result=False)
    if not result.valid:
        raise AuditorError("configuration_analysis_invalid", "実行構成を結び付けるanalysis.jsonが検証に合格していません。")

    record = {
        "format_version": "1",
        "case_id": case["case_id"],
        "proposal_sha256": case["proposal_sha256"],
        "analysis_perspective": case.get("analysis_perspective", "general"),
        "analysis_sha256": sha256_file(analysis_path),
        "model_display_name": model,
        "reasoning_setting": reasoning,
        "evidence_source": evidence_source,
        "explicitly_recorded": evidence_source != "unavailable",
        "inference_used": False,
        "recorded_at": utc_now(),
        "limitation": (
            "記録値は指定された証拠元で明示的に確認できた範囲だけです。"
            "未記録の設定や完全な構成同一性を示しません。"
        ),
    }
    atomic_write_json(destination, record)
    return record


def load_run_configuration(case_dir: Path, analysis_sha256: str) -> dict[str, Any]:
    path = case_dir / "run-configuration.json"
    if not path.exists():
        return {
            "model_display_name": None,
            "reasoning_setting": None,
            "evidence_source": "not_recorded",
            "explicitly_recorded": False,
            "inference_used": False,
        }
    if not path.is_file() or path.is_symlink():
        raise AuditorError("invalid_configuration_record", "実行構成記録は通常ファイルである必要があります。")
    value = load_json(path)
    if not isinstance(value, dict):
        raise AuditorError("invalid_configuration_record", "実行構成記録が正しくありません。")
    required = {
        "case_id",
        "proposal_sha256",
        "analysis_perspective",
        "analysis_sha256",
        "model_display_name",
        "reasoning_setting",
        "evidence_source",
        "explicitly_recorded",
        "inference_used",
    }
    if not required.issubset(value):
        raise AuditorError("invalid_configuration_record", "実行構成記録の必須フィールドが不足しています。")
    case, _ = read_case(case_dir)
    if value["case_id"] != case.get("case_id") or value["proposal_sha256"] != case.get("proposal_sha256"):
        raise AuditorError("configuration_binding_mismatch", "実行構成記録が現在のケースと一致しません。")
    if value["analysis_perspective"] != case.get("analysis_perspective", "general"):
        raise AuditorError("configuration_binding_mismatch", "実行構成記録の視点が現在のケースと一致しません。")
    if value["analysis_sha256"] != analysis_sha256:
        raise AuditorError("configuration_analysis_changed", "実行構成記録後にanalysis.jsonが変更されています。")
    source = value.get("evidence_source")
    if source not in CONFIGURATION_EVIDENCE_SOURCES:
        raise AuditorError("invalid_configuration_record", "実行構成記録の証拠元が正しくありません。")
    model = value.get("model_display_name")
    reasoning = value.get("reasoning_setting")
    if model is not None and not isinstance(model, str):
        raise AuditorError("invalid_configuration_record", "モデル表示名の型が正しくありません。")
    if reasoning is not None and not isinstance(reasoning, str):
        raise AuditorError("invalid_configuration_record", "推論設定の型が正しくありません。")
    if model is not None and _explicit_value(model, "モデル表示名") != model:
        raise AuditorError("invalid_configuration_record", "モデル表示名が正規化済みではありません。")
    if reasoning is not None and _explicit_value(reasoning, "推論設定") != reasoning:
        raise AuditorError("invalid_configuration_record", "推論設定が正規化済みではありません。")
    expected_explicit = source != "unavailable"
    if value.get("explicitly_recorded") is not expected_explicit or value.get("inference_used") is not False:
        raise AuditorError("invalid_configuration_record", "明示記録または推論使用の表示が正しくありません。")
    if source == "unavailable" and (model is not None or reasoning is not None):
        raise AuditorError("invalid_configuration_record", "unavailableの実行構成記録に推測値があります。")
    if source != "unavailable" and model is None and reasoning is None:
        raise AuditorError("invalid_configuration_record", "明示的な証拠元に記録値がありません。")
    return {
        "model_display_name": model,
        "reasoning_setting": reasoning,
        "evidence_source": source,
        "explicitly_recorded": expected_explicit,
        "inference_used": False,
    }


def summarize_configuration(records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    pairs = [
        (record.get("model_display_name"), record.get("reasoning_setting"))
        for record in records.values()
    ]
    complete = all(
        record.get("explicitly_recorded") is True and pair[0] is not None and pair[1] is not None
        for record, pair in zip(records.values(), pairs, strict=True)
    )
    if not complete:
        relationship = "incomplete"
        reason = "3視点すべてについてモデル表示名と推論設定が明示記録されていません。"
    elif len(set(pairs)) == 1:
        relationship = "recorded_fields_match"
        reason = "明示記録されたモデル表示名と推論設定は一致しますが、未記録設定を含む完全な同一性は示しません。"
    else:
        relationship = "recorded_fields_differ"
        reason = "明示記録されたモデル表示名または推論設定が視点間で異なります。"
    return {
        "configuration_comparability": "not_demonstrated",
        "recorded_field_relationship": relationship,
        "reason": reason,
        "inference_used": False,
    }


def _load_comparison(comparison_dir: Path) -> tuple[dict[str, Any], Path, Path]:
    json_path = comparison_dir / "perspective-comparison.json"
    markdown_path = comparison_dir / "perspective-comparison-ja.md"
    for path in (json_path, markdown_path):
        if not path.is_file() or path.is_symlink():
            raise AuditorError("comparison_file_missing", "比較JSONとMarkdownの通常ファイルが必要です。")
    value = load_json(json_path)
    if not isinstance(value, dict):
        raise AuditorError("invalid_comparison", "比較JSONが正しくありません。")
    if value.get("human_review_required") is not True or not isinstance(value.get("axes"), list):
        raise AuditorError("invalid_comparison", "人間確認必須の比較JSONではありません。")
    if len(value["axes"]) != 11:
        raise AuditorError("invalid_comparison", "比較JSONの11軸がそろっていません。")
    return value, json_path, markdown_path


def record_comparison_review(
    comparison_dir: Path,
    *,
    review_state: str,
    reviewer_label: str,
    independence_status: str,
    independence_basis: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    if review_state not in REVIEW_STATES:
        raise AuditorError("invalid_comparison_review_state", "比較レビュー状態が許可されていません。")
    if LABEL_PATTERN.fullmatch(reviewer_label) is None:
        raise AuditorError("invalid_reviewer_label", "担当者ラベルは匿名の英数字・ハイフン・下線にしてください。")
    if independence_status not in INDEPENDENCE_STATUSES:
        raise AuditorError("invalid_independence_status", "独立性状態が許可されていません。")
    basis = independence_basis.strip() if independence_basis else None
    if independence_status == "independent" and not basis:
        raise AuditorError("independence_basis_required", "independentの記録には独立性の根拠が必要です。")
    for label, value, limit in (("独立性の根拠", basis, 500), ("レビューメモ", note, 1_000)):
        if value is not None:
            if len(value) > limit:
                raise AuditorError("review_text_too_long", f"{label}は{limit}文字以内にしてください。")
            if sensitive_categories(value):
                raise AuditorError("sensitive_review_text", f"{label}に秘密情報または個人情報の可能性があります。")

    comparison, json_path, markdown_path = _load_comparison(comparison_dir)
    reviews_dir = comparison_dir / "comparison-reviews"
    if reviews_dir.exists() and (not reviews_dir.is_dir() or reviews_dir.is_symlink()):
        raise AuditorError("unsafe_review_directory", "比較レビュー用フォルダが安全ではありません。")
    destination = reviews_dir / f"{reviewer_label}.json"
    if destination.exists():
        raise AuditorError("comparison_review_exists", "同じ担当者ラベルの比較レビューが既にあります。")
    reviews_dir.mkdir(parents=False, exist_ok=True)

    record = {
        "format_version": "1",
        "review_scope": "three_perspective_structural_comparison",
        "proposal_sha256": comparison.get("proposal_sha256"),
        "comparison_method": comparison.get("comparison_method"),
        "comparison_json_sha256": sha256_file(json_path),
        "comparison_markdown_sha256": sha256_file(markdown_path),
        "review_state": review_state,
        "reviewer_label": reviewer_label,
        "independence_status": independence_status,
        "independence_basis": basis,
        "independence_is_self_attested": True,
        "reviewed_at": utc_now(),
        "meaning": REVIEW_MEANING,
        "limitations": [
            "独立性は担当者による自己申告であり、ツールが外部証拠で検証したものではありません。",
            "この記録は比較結果の確認を示し、元提案や個別監査結果の承認を意味しません。",
        ],
    }
    if note:
        record["note"] = note
    atomic_write_json(destination, record)
    return record


def comparison_review_status(comparison_dir: Path) -> dict[str, Any]:
    comparison, json_path, markdown_path = _load_comparison(comparison_dir)
    expected_json = sha256_file(json_path)
    expected_markdown = sha256_file(markdown_path)
    reviews_dir = comparison_dir / "comparison-reviews"
    summary = {
        "reviews_total": 0,
        "reviewed_count": 0,
        "needs_revision_count": 0,
        "independent_reviewed_count": 0,
        "not_independent_reviewed_count": 0,
        "unknown_independence_reviewed_count": 0,
        "invalid_count": 0,
    }
    if not reviews_dir.exists():
        return summary
    if not reviews_dir.is_dir() or reviews_dir.is_symlink():
        raise AuditorError("unsafe_review_directory", "比較レビュー用フォルダが安全ではありません。")
    for path in sorted(reviews_dir.iterdir()):
        if path.suffix != ".json" or not path.is_file() or path.is_symlink():
            summary["invalid_count"] += 1
            continue
        summary["reviews_total"] += 1
        try:
            value = load_json(path)
        except AuditorError:
            summary["invalid_count"] += 1
            continue
        valid_record = (
            isinstance(value, dict)
            and value.get("review_scope") == "three_perspective_structural_comparison"
            and value.get("proposal_sha256") == comparison.get("proposal_sha256")
            and value.get("comparison_method") == comparison.get("comparison_method")
            and value.get("comparison_json_sha256") == expected_json
            and value.get("comparison_markdown_sha256") == expected_markdown
            and value.get("reviewer_label") == path.stem
            and LABEL_PATTERN.fullmatch(str(value.get("reviewer_label", ""))) is not None
            and value.get("independence_is_self_attested") is True
            and value.get("meaning") == REVIEW_MEANING
            and isinstance(value.get("limitations"), list)
            and bool(value.get("limitations"))
        )
        if not valid_record:
            summary["invalid_count"] += 1
            continue
        state = value.get("review_state")
        independence = value.get("independence_status")
        if independence == "independent" and not value.get("independence_basis"):
            summary["invalid_count"] += 1
            continue
        if state == "reviewed" and independence in INDEPENDENCE_STATUSES:
            summary["reviewed_count"] += 1
            counter = {
                "independent": "independent_reviewed_count",
                "not_independent": "not_independent_reviewed_count",
                "unknown": "unknown_independence_reviewed_count",
            }[independence]
            summary[counter] += 1
        elif state == "needs_revision":
            summary["needs_revision_count"] += 1
        else:
            summary["invalid_count"] += 1
    return summary
