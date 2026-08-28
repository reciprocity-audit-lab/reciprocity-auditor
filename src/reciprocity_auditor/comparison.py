from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .errors import AuditorError
from .evaluation import load_run_configuration, summarize_configuration
from .io_utils import read_case, sha256_file, validate_case_id, write_new_text
from .validation import validate_analysis


PERSPECTIVE_NAMES = ("justice", "reversal", "tower")
STATUS_NAMES = ("consistent", "complementary", "tension", "direct_conflict", "cannot_compare")


@dataclass(frozen=True, slots=True)
class Observation:
    facts: tuple[str, ...] = ()
    positions: tuple[tuple[str, str], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {"facts": list(self.facts), "positions": dict(self.positions)}


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    output_dir: Path
    json_path: Path
    markdown_path: Path
    summary: dict[str, int]


def _text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value.strip()).casefold()


def _facts(values: list[str]) -> tuple[str, ...]:
    return tuple(sorted({value for value in values if value}))


def _allocations(data: dict[str, Any], fields: tuple[str, ...]) -> Observation:
    values: list[str] = []
    for field in fields:
        for item in data.get(field, []):
            if not isinstance(item, dict):
                continue
            actor = _text(item.get("actor_id"))
            counterparties = ",".join(sorted(_text(v) for v in item.get("counterparty_ids", []) if _text(v)))
            description = _text(item.get("description"))
            values.append(f"{field}:{actor}:{counterparties}:{description}")
    return Observation(_facts(values))


def _subjects(data: dict[str, Any]) -> Observation:
    return Observation(
        _facts(
            [f"{_text(item.get('id'))}:{_text(item.get('name'))}" for item in data.get("actors", []) if isinstance(item, dict)]
        )
    )


def _missed_subjects(data: dict[str, Any]) -> Observation:
    return Observation(
        _facts([_text(item.get("name")) for item in data.get("affected_non_parties", []) if isinstance(item, dict)])
    )


def _exceptions(data: dict[str, Any]) -> Observation:
    values = [
        f"exception:{_text(item.get('actor_id'))}:{_text(item.get('description'))}"
        for item in data.get("exceptions", [])
        if isinstance(item, dict)
    ]
    for issue in data.get("detected_issues", []):
        if isinstance(issue, dict) and issue.get("issue_type") in {"self_exemption", "unilateral_privilege"}:
            values.append(f"issue:{issue['issue_type']}:{','.join(sorted(map(_text, issue.get('actor_ids', []))))}")
    return Observation(_facts(values))


def _reversibility(data: dict[str, Any]) -> Observation:
    values: list[str] = []
    for item in data.get("reversibility_test", []):
        if isinstance(item, dict):
            roles = ",".join(sorted(_text(v) for v in item.get("roles_swapped", [])))
            values.append(f"{roles}:{_text(item.get('result'))}")
    return Observation(_facts(values))


def _reasonable_asymmetry(data: dict[str, Any]) -> Observation:
    values: list[str] = []
    for item in data.get("reversibility_test", []):
        if isinstance(item, dict):
            values.extend(f"difference:{_text(value)}" for value in item.get("relevant_differences", []))
    for issue in data.get("detected_issues", []):
        if isinstance(issue, dict) and issue.get("counter_interpretation"):
            values.append(f"counter:{_text(issue.get('issue_type'))}:{_text(issue.get('counter_interpretation'))}")
    return Observation(_facts(values))


def _missing_information(data: dict[str, Any]) -> Observation:
    values: list[str] = []
    for item in data.get("missing_information", []):
        if isinstance(item, dict):
            fields = ",".join(sorted(_text(value) for value in item.get("affected_fields", [])))
            values.append(f"{fields}:{_text(item.get('question'))}")
    return Observation(_facts(values))


def _opposite_interpretation(data: dict[str, Any]) -> Observation:
    values = [
        f"alternative:{_text(item.get('interpretation'))}"
        for item in data.get("alternative_interpretations", [])
        if isinstance(item, dict)
    ]
    for issue in data.get("detected_issues", []):
        if isinstance(issue, dict) and issue.get("counter_interpretation"):
            values.append(f"issue:{_text(issue.get('issue_type'))}:{_text(issue.get('counter_interpretation'))}")
    return Observation(_facts(values))


def _improvement_questions(data: dict[str, Any]) -> Observation:
    values: list[str] = []
    for field in ("affected_non_parties", "reversibility_test", "detected_issues"):
        for item in data.get(field, []):
            if isinstance(item, dict):
                values.extend(_text(value) for value in item.get("questions", []))
    values.extend(
        _text(item.get("question"))
        for item in data.get("missing_information", [])
        if isinstance(item, dict)
    )
    return Observation(_facts(values))


def _cannot_assess(data: dict[str, Any]) -> Observation:
    values: list[str] = []
    for issue in data.get("detected_issues", []):
        if isinstance(issue, dict) and issue.get("issue_type") in {"cannot_assess", "evidence_gap"}:
            values.append(f"issue:{issue['issue_type']}:{','.join(sorted(map(_text, issue.get('actor_ids', []))))}")
    positions: list[tuple[str, str]] = []
    for field in ("enforcement", "oversight", "appeals"):
        item = data.get(field)
        if isinstance(item, dict) and isinstance(item.get("defined"), bool):
            positions.append((f"{field}.defined", str(item["defined"]).lower()))
    return Observation(_facts(values), tuple(sorted(positions)))


AXES: tuple[tuple[str, Callable[[dict[str, Any]], Observation]], ...] = (
    ("extracted_subjects", _subjects),
    ("possibly_missed_subjects", _missed_subjects),
    ("rights_benefits", lambda data: _allocations(data, ("rights", "benefits"))),
    ("responsibility_burden_risk", lambda data: _allocations(data, ("responsibilities", "burdens", "risks"))),
    ("exceptions_self_exceptions", _exceptions),
    ("reversibility", _reversibility),
    ("reasonable_asymmetry", _reasonable_asymmetry),
    ("missing_information", _missing_information),
    ("opposite_interpretation", _opposite_interpretation),
    ("improvement_questions", _improvement_questions),
    ("ai_cannot_assess", _cannot_assess),
)


def _has_direct_conflict(observations: dict[str, Observation]) -> bool:
    by_key: dict[str, set[str]] = {}
    for observation in observations.values():
        for key, value in observation.positions:
            by_key.setdefault(key, set()).add(value)
    return any(values == {"true", "false"} for values in by_key.values())


def _classify(observations: dict[str, Observation]) -> tuple[str, str]:
    if _has_direct_conflict(observations):
        return "direct_conflict", "同じ構造化真偽値についてtrueとfalseが明示されています。"

    signatures = [
        set(observation.facts) | {f"{key}={value}" for key, value in observation.positions}
        for observation in observations.values()
    ]
    nonempty = [signature for signature in signatures if signature]
    if not nonempty:
        return "cannot_compare", "比較可能な正規化済み項目がありません。"
    if len(nonempty) == 3 and signatures[0] == signatures[1] == signatures[2]:
        return "consistent", "3視点の正規化済み項目が一致しています。"
    if len(nonempty) == 1:
        return "complementary", "1視点だけが正規化可能な項目を追加しています。"

    nested = all(left <= right or right <= left for left in nonempty for right in nonempty)
    if nested:
        return "complementary", "視点間の差は、共通項目への追加として整理できます。"
    return "tension", "複数視点に比較可能な項目がありますが、追加関係だけでは整理できません。"


def _load_perspective(case_dir: Path, expected: str) -> tuple[dict[str, Any], dict[str, Any], str, dict[str, Any]]:
    case, _ = read_case(case_dir)
    validate_case_id(str(case.get("case_id", "")))
    actual = case.get("analysis_perspective")
    if actual != expected:
        raise AuditorError(
            "perspective_mismatch",
            f"{expected}ケースのanalysis_perspectiveが{expected}ではありません。",
        )
    analysis_path = case_dir / "analysis.json"
    result = validate_analysis(analysis_path, write_result=False)
    if not result.valid or result.data is None:
        raise AuditorError("comparison_validation_failed", f"{expected}のanalysis.jsonが検証に合格していません。")
    analysis_sha256 = sha256_file(analysis_path)
    configuration = load_run_configuration(case_dir, analysis_sha256)
    return case, result.data, analysis_sha256, configuration


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 3視点の決定的横断比較",
        "",
        "この報告はJustice・Reversal・Towerの検証済みJSONを、Schema上の構造化項目だけで比較したものです。文章の意味的同一性、公平性、適法性、採否、執行、処罰を判断しません。",
        "",
        f"- proposal_sha256: `{payload['proposal_sha256']}`",
        "- comparison_method: `structural-v0.2`",
        f"- configuration_comparability: `{payload['configuration_summary']['configuration_comparability']}`",
        f"- recorded_field_relationship: `{payload['configuration_summary']['recorded_field_relationship']}`",
        "- human_review_required: `true`",
        "",
        "## 集計",
        "",
    ]
    for status in STATUS_NAMES:
        lines.append(f"- `{status}`: {payload['summary'][status]}")
    lines.extend(["", "## 11比較軸", "", "| 軸 | 結果 | 理由 |", "|---|---|---|"])
    for axis in payload["axes"]:
        lines.append(f"| `{axis['axis']}` | `{axis['status']}` | {axis['reason']} |")
    lines.extend(
        [
            "",
            "## 読み方と限界",
            "",
            "- `consistent`は正規化済み項目の一致であり、共通の見落としがないことを証明しません。",
            "- `complementary`は、一方の視点が他方へ構造化項目を追加した状態です。",
            "- `tension`は差異を示しますが、どちらが正しいかを決めません。",
            "- `direct_conflict`は、同じ構造化真偽値に明示的な反対値がある場合だけ使用します。",
            "- `cannot_compare`は、比較材料がない状態です。問題が存在しないことを意味しません。",
            "- 自由記述の言い換えや意味的同等性は判定しません。独立した人間レビューが必要です。",
            f"- 実行構成: {payload['configuration_summary']['reason']}",
            "",
            "## 最終責任",
            "",
            payload["disclaimer"],
            "",
        ]
    )
    return "\n".join(lines)


def compare_perspectives(
    *,
    justice_case: Path,
    reversal_case: Path,
    tower_case: Path,
    output_dir: Path,
) -> ComparisonResult:
    if output_dir.exists():
        raise AuditorError("output_exists", "比較結果の出力フォルダが既に存在します。上書きしません。")

    source_dirs = {"justice": justice_case, "reversal": reversal_case, "tower": tower_case}
    resolved_output = output_dir.resolve(strict=False)
    for source_dir in source_dirs.values():
        resolved_source = source_dir.resolve(strict=False)
        if resolved_output == resolved_source or resolved_source in resolved_output.parents:
            raise AuditorError("unsafe_output_location", "比較結果は3つの元ケースの外へ出力してください。")
    loaded: dict[str, tuple[dict[str, Any], dict[str, Any], str, dict[str, Any]]] = {}
    for perspective in PERSPECTIVE_NAMES:
        loaded[perspective] = _load_perspective(source_dirs[perspective], perspective)

    proposal_hashes = {item[0].get("proposal_sha256") for item in loaded.values()}
    if len(proposal_hashes) != 1:
        raise AuditorError("proposal_hash_mismatch", "3視点の提案SHA-256が一致しません。")
    proposal_sha256 = str(next(iter(proposal_hashes)))
    configurations = {
        perspective: loaded[perspective][3]
        for perspective in PERSPECTIVE_NAMES
    }

    axes: list[dict[str, Any]] = []
    summary = {status: 0 for status in STATUS_NAMES}
    for axis_name, extractor in AXES:
        observations = {
            perspective: extractor(loaded[perspective][1])
            for perspective in PERSPECTIVE_NAMES
        }
        status, reason = _classify(observations)
        summary[status] += 1
        axes.append(
            {
                "axis": axis_name,
                "status": status,
                "reason": reason,
                "normalized": {
                    perspective: observations[perspective].as_dict()
                    for perspective in PERSPECTIVE_NAMES
                },
            }
        )

    payload = {
        "format_version": "0.2.0",
        "comparison_method": "structural-v0.2",
        "proposal_sha256": proposal_sha256,
        "sources": {
            perspective: {
                "case_id": loaded[perspective][0]["case_id"],
                "analysis_perspective": perspective,
                "analysis_sha256": loaded[perspective][2],
                "run_configuration": configurations[perspective],
            }
            for perspective in PERSPECTIVE_NAMES
        },
        "configuration_summary": summarize_configuration(configurations),
        "axes": axes,
        "summary": summary,
        "human_review_required": True,
        "limitations": [
            "構造化された値だけを比較し、自由記述の意味的同等性は判定しない。",
            "一致は共通の見落としがないことを証明しない。",
            "モデル名や推論設定を推測せず、独立モデル評価を主張しない。",
        ],
        "disclaimer": "法的助言ではありません。公平性、善悪、適法性、採否、執行、処罰を自動決定せず、人間による原文・証拠・文脈の確認が必要です。",
    }

    output_dir.mkdir(parents=True, exist_ok=False)
    try:
        json_path = output_dir / "perspective-comparison.json"
        markdown_path = output_dir / "perspective-comparison-ja.md"
        write_new_text(json_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        write_new_text(markdown_path, _render_markdown(payload))
    except Exception:
        shutil.rmtree(output_dir)
        raise
    return ComparisonResult(output_dir, json_path, markdown_path, summary)
