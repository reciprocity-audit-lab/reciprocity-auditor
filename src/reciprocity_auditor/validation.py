from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import AuditorError, ValidationFinding
from .io_utils import (
    append_event,
    atomic_write_json,
    decode_utf8,
    project_root,
    read_case,
    read_limited_bytes,
    sensitive_categories,
    sha256_file,
    update_state,
    utc_now,
)


BANNED_CONCLUSIONS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("legal_conclusion", re.compile(r"(?:明らかに|確実に|必ず)?(?:違法|合法)(?:です|である|だ)(?:[。\s]|$)")),
    ("moral_conclusion", re.compile(r"(?:絶対に|明らかに)?(?:善|悪)(?:です|である|だ)(?:[。\s]|$)")),
    ("fairness_conclusion", re.compile(r"(?:完全に|明らかに)?(?:公平|不公平|公正|不公正)(?:です|である|だ)(?:[。\s]|$)")),
    ("adoption_instruction", re.compile(r"(?:採択|拒否|承認|否決)(?:すべき|しなければならない)")),
    ("punishment_instruction", re.compile(r"(?:処罰|制裁|没収|停止)(?:すべき|しなければならない)")),
    ("guilt_conclusion", re.compile(r"(?:有罪|詐欺)(?:です|である|だ)(?:[。\s]|$)")),
    ("overall_score", re.compile(r"(?:公平|公正)(?:度|性)?\s*[:：]?\s*\d{1,3}\s*(?:点|%)")),
)


@dataclass(slots=True)
class ValidationResult:
    valid: bool
    findings: list[ValidationFinding]
    data: dict[str, Any] | None
    case_id: str
    proposal_sha256: str


def _json_type_matches(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    return True


def _resolve_ref(root_schema: dict[str, Any], ref: str) -> dict[str, Any] | None:
    if not ref.startswith("#/"):
        return None
    current: Any = root_schema
    for segment in ref[2:].split("/"):
        segment = segment.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or segment not in current:
            return None
        current = current[segment]
    return current if isinstance(current, dict) else None


def _schema_findings(
    value: Any,
    schema: dict[str, Any],
    root_schema: dict[str, Any],
    path: str = "$",
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    if "$ref" in schema:
        resolved = _resolve_ref(root_schema, schema["$ref"])
        if resolved is None:
            return [ValidationFinding("schema_reference_error", path, "内部Schema参照を解決できません。")]
        return _schema_findings(value, resolved, root_schema, path)

    expected = schema.get("type")
    if expected is not None:
        expected_types = [expected] if isinstance(expected, str) else expected
        if not any(_json_type_matches(value, item) for item in expected_types):
            return [ValidationFinding("wrong_type", path, "値の型が必要な形式と一致しません。")]

    if "const" in schema and value != schema["const"]:
        findings.append(ValidationFinding("const_mismatch", path, "固定値と一致しません。"))
    if "enum" in schema and value not in schema["enum"]:
        findings.append(ValidationFinding("enum_not_allowed", path, "許可されていない値です。"))

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            findings.append(ValidationFinding("string_too_short", path, "必須の説明が不足しています。"))
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            findings.append(ValidationFinding("string_too_long", path, "文字列が上限を超えています。"))
        if "pattern" in schema and re.fullmatch(schema["pattern"], value) is None:
            findings.append(ValidationFinding("pattern_mismatch", path, "文字列の形式が正しくありません。"))

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            findings.append(ValidationFinding("number_below_minimum", path, "数値が下限未満です。"))
        if "maximum" in schema and value > schema["maximum"]:
            findings.append(ValidationFinding("number_above_maximum", path, "数値が上限を超えています。"))

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            findings.append(ValidationFinding("array_too_short", path, "配列の項目が不足しています。"))
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            findings.append(ValidationFinding("array_too_long", path, "配列の項目が上限を超えています。"))
        if schema.get("uniqueItems"):
            normalized = [json.dumps(item, ensure_ascii=False, sort_keys=True) for item in value]
            if len(normalized) != len(set(normalized)):
                findings.append(ValidationFinding("duplicate_array_item", path, "配列に重複があります。"))
        if isinstance(schema.get("items"), dict):
            for index, item in enumerate(value):
                findings.extend(_schema_findings(item, schema["items"], root_schema, f"{path}[{index}]"))

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                findings.append(ValidationFinding("required_missing", f"{path}.{key}", "必須フィールドがありません。"))
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    findings.append(ValidationFinding("additional_property", f"{path}.{key}", "未定義のフィールドです。"))
        for key, subschema in properties.items():
            if key in value and isinstance(subschema, dict):
                findings.extend(_schema_findings(value[key], subschema, root_schema, f"{path}.{key}"))
    return findings


def _authored_texts(value: Any, path: str = "$") -> list[tuple[str, str]]:
    output: list[tuple[str, str]] = []
    if path.startswith("$.disclaimer") or ".evidence_refs" in path:
        return output
    if isinstance(value, str):
        output.append((path, value))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            output.extend(_authored_texts(item, f"{path}[{index}]"))
    elif isinstance(value, dict):
        for key, item in value.items():
            output.extend(_authored_texts(item, f"{path}.{key}"))
    return output


def _project_findings(data: dict[str, Any], case: dict[str, Any]) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    metadata = data.get("audit_metadata")
    if not isinstance(metadata, dict):
        findings.append(ValidationFinding("audit_metadata_required", "$.audit_metadata", "MVPでは監査メタデータが必須です。"))
    elif metadata.get("report_id") != case.get("case_id"):
        findings.append(ValidationFinding("case_id_mismatch", "$.audit_metadata.report_id", "ケースIDが準備済みケースと一致しません。"))

    disclaimer = data.get("disclaimer")
    if not isinstance(disclaimer, str) or not all(token in disclaimer for token in ("法的助言", "人間")):
        findings.append(ValidationFinding("disclaimer_incomplete", "$.disclaimer", "法的助言ではなく人間確認が必要である旨が不足しています。"))
    elif "採択" not in disclaimer and "処罰" not in disclaimer:
        findings.append(ValidationFinding("disclaimer_incomplete", "$.disclaimer", "採択または処罰を自動化しない旨が不足しています。"))

    issue_types = {
        item.get("issue_type")
        for item in data.get("detected_issues", [])
        if isinstance(item, dict)
    }
    if issue_types.intersection({"evidence_gap", "cannot_assess"}):
        if not data.get("missing_information"):
            findings.append(ValidationFinding("missing_information_required", "$.missing_information", "情報不足の問題候補には不足情報が必要です。"))
        if not data.get("evidence_needed"):
            findings.append(ValidationFinding("evidence_needed_required", "$.evidence_needed", "情報不足の問題候補には必要証拠が必要です。"))

    for path, text in _authored_texts(data):
        for code, pattern in BANNED_CONCLUSIONS:
            if pattern.search(text):
                findings.append(ValidationFinding("prohibited_conclusion", path, f"禁止された最終断定の候補です（{code}）。"))
                break
    return findings


def _write_validation_result(
    case_dir: Path,
    case: dict[str, Any],
    state: dict[str, Any],
    findings: list[ValidationFinding],
) -> None:
    valid = not findings
    checked_at = utc_now()
    atomic_write_json(
        case_dir / "validation.json",
        {
            "valid": valid,
            "case_id": case["case_id"],
            "proposal_sha256": case["proposal_sha256"],
            "checked_at": checked_at,
            "errors": [finding.as_dict() for finding in findings],
        },
    )
    update_state(
        case_dir,
        state,
        analysis_status="present",
        validation_status="valid" if valid else "failed",
    )
    append_event(
        case_dir,
        case_id=case["case_id"],
        proposal_sha256=case["proposal_sha256"],
        event="validate",
        state="valid" if valid else "failed",
        error_code=None if valid else findings[0].code,
    )


def validate_analysis(input_path: Path, *, write_result: bool = True) -> ValidationResult:
    case_dir = input_path.parent
    case, state = read_case(case_dir)
    findings: list[ValidationFinding] = []

    if case.get("proposal_file") != "proposal.txt":
        findings.append(ValidationFinding("invalid_proposal_reference", "$.case.proposal_file", "提案ファイル参照が正しくありません。"))
    proposal_path = case_dir / "proposal.txt"
    if not proposal_path.is_file() or sha256_file(proposal_path) != case.get("proposal_sha256"):
        findings.append(ValidationFinding("proposal_hash_mismatch", "$.case.proposal_sha256", "提案ハッシュが準備時と一致しません。"))

    data: dict[str, Any] | None = None
    try:
        raw = read_limited_bytes(input_path)
        text = decode_utf8(raw)
        if sensitive_categories(text):
            findings.append(ValidationFinding("sensitive_analysis_detected", "$", "AI回答に秘密情報または個人情報の可能性があります。"))
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            findings.append(ValidationFinding("top_level_not_object", "$", "JSONの最上位はオブジェクトである必要があります。"))
        else:
            data = parsed
    except json.JSONDecodeError:
        findings.append(ValidationFinding("invalid_json", "$", "JSON構文が正しくありません。"))
    except AuditorError as exc:
        findings.append(ValidationFinding(exc.code, "$", exc.message))

    if data is not None:
        schema_path = project_root() / "docs" / "phase1" / "AUDIT-SCHEMA.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        findings.extend(_schema_findings(data, schema, schema))
        findings.extend(_project_findings(data, case))

    if write_result:
        _write_validation_result(case_dir, case, state, findings)
    return ValidationResult(
        valid=not findings,
        findings=findings,
        data=data,
        case_id=str(case.get("case_id", "unknown")),
        proposal_sha256=str(case.get("proposal_sha256", "unknown")),
    )
