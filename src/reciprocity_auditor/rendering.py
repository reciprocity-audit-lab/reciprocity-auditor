from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .errors import AuditorError
from .io_utils import (
    append_event,
    atomic_write_text,
    load_json,
    read_case,
    sha256_file,
    update_state,
    utc_now,
    write_new_bytes,
)
from .validation import validate_analysis
from .workflow import report_file_from_state, review_integrity


LEVEL_LABELS = {
    "clear_issue_candidate": "明確な問題候補",
    "needs_attention": "注意・追加確認が必要",
    "insufficient_information": "情報不足で判断不能",
}
REVIEW_HISTORY_DIR = "review-history"


def _archive_review_context(case_dir: Path, state: dict[str, Any]) -> tuple[Path, Path | None] | None:
    review_path = case_dir / "review.json"
    if not review_path.exists():
        return None
    if not review_path.is_file() or review_path.is_symlink():
        raise AuditorError("invalid_review_file", "現在の人間レビュー記録が正しくありません。")

    review = load_json(review_path)
    if not isinstance(review, dict):
        raise AuditorError("invalid_review_file", "現在の人間レビュー記録が正しくありません。")
    report_file = review.get("report_file", report_file_from_state(state))
    if not isinstance(report_file, str) or not report_file or Path(report_file).name != report_file:
        raise AuditorError("invalid_review_file", "レビュー対象の監査報告書名が正しくありません。")
    reviewed_report = case_dir / report_file
    if reviewed_report.exists() and (not reviewed_report.is_file() or reviewed_report.is_symlink()):
        raise AuditorError("invalid_reviewed_report", "レビュー対象の監査報告書が正しくありません。")

    history_dir = case_dir / REVIEW_HISTORY_DIR
    if history_dir.exists() or history_dir.is_symlink():
        if not history_dir.is_dir() or history_dir.is_symlink():
            raise AuditorError("unsafe_review_history", "レビュー履歴フォルダが安全な通常フォルダではありません。")
    else:
        history_dir.mkdir(parents=False, exist_ok=False)
    index = 1
    while True:
        archived_review = history_dir / f"review-{index:04d}.json"
        archived_report = history_dir / f"audit-report-{index:04d}.md"
        if archived_review.is_symlink() or archived_report.is_symlink():
            raise AuditorError("unsafe_review_history", "レビュー履歴にシンボリックリンクは使用できません。")
        if not archived_review.exists() and not archived_report.exists():
            break
        index += 1

    write_new_bytes(archived_review, review_path.read_bytes())
    report_archive: Path | None = None
    try:
        if reviewed_report.is_file():
            write_new_bytes(archived_report, reviewed_report.read_bytes())
            report_archive = archived_report
    except Exception:
        archived_review.unlink(missing_ok=True)
        raise
    return archived_review, report_archive


def _discard_failed_archive(archive: tuple[Path, Path | None] | None) -> None:
    if archive is None:
        return
    archived_review, archived_report = archive
    archived_review.unlink(missing_ok=True)
    if archived_report is not None:
        archived_report.unlink(missing_ok=True)
    history_dir = archived_review.parent
    try:
        history_dir.rmdir()
    except OSError:
        pass


def _text(value: Any, default: str = "明記なし") -> str:
    if value is None or value == "":
        return default
    return str(value).replace("\r", " ").replace("\n", " ").strip()


def _bullets(values: Iterable[Any], *, empty: str = "- なし、または明記なし") -> list[str]:
    items = [f"- {_text(value)}" for value in values if value is not None and _text(value, "")]
    return items or [empty]


def _evidence_status(item: dict[str, Any]) -> str:
    refs = item.get("evidence_refs", [])
    if not refs:
        return "根拠参照なし"
    statuses = sorted({str(ref.get("status", "unknown")) for ref in refs if isinstance(ref, dict)})
    return ", ".join(statuses) if statuses else "根拠参照なし"


def _render_allocations(title: str, items: list[dict[str, Any]]) -> list[str]:
    lines = [f"### {title}", ""]
    if not items:
        return lines + ["- なし、または明記なし", ""]
    for item in items:
        lines.extend(
            [
                f"- **主体 `{_text(item.get('actor_id'))}`**: {_text(item.get('description'))}",
                f"  - 相手方: {_text(', '.join(item.get('counterparty_ids', [])))}",
                f"  - 条件: {_text(item.get('conditions'))}",
                f"  - 期間: {_text(item.get('duration'))}",
                f"  - 対応項目: {_text(item.get('reciprocal_item'))}",
                f"  - 根拠状態: {_evidence_status(item)}",
            ]
        )
        if "likelihood" in item:
            lines.append(f"  - 発生可能性／影響: {_text(item.get('likelihood'))} / {_text(item.get('impact_severity'))}")
    lines.append("")
    return lines


def render_markdown(data: dict[str, Any], *, case_id: str, proposal_sha256: str) -> str:
    summary = data["proposal_summary"]
    confidence = data["confidence"]
    lines: list[str] = [
        "# 相互性監査報告書",
        "",
        "> この報告は契約構造と手続上の問題候補を整理するものです。法的助言ではなく、採択・拒否・処罰の決定ではありません。人間による確認が必要です。",
        "",
        "## 1. 基本情報",
        "",
        f"- ケースID: `{case_id}`",
        f"- 提案SHA-256: `{proposal_sha256}`",
        f"- Schema版: `{_text(data.get('audit_metadata', {}).get('schema_version'))}`",
        f"- 入力状態: `{_text(summary.get('source_status'))}`",
        f"- 生成日時: `{utc_now()}`",
        "",
        "## 2. 提案の要約",
        "",
        _text(summary.get("summary")),
        "",
        f"- 提案が述べる目的: {_text(summary.get('stated_purpose'))}",
        f"- 適用範囲: {_text(summary.get('scope'))}",
        "",
        "## 3. 契約主体",
        "",
    ]

    actors = data.get("actors", [])
    if not actors:
        lines.extend(["- なし、または明記なし", ""])
    else:
        for actor in actors:
            lines.extend(
                [
                    f"### {_text(actor.get('name'))} (`{_text(actor.get('id'))}`)",
                    "",
                    f"- 役割: {_text(', '.join(actor.get('roles', [])))}",
                    f"- 当事者区分: {_text(actor.get('party_status'))}",
                    f"- 同意方法: {_text(actor.get('consent_mechanism'))}",
                    f"- 退出方法: {_text(actor.get('exit_mechanism'))}",
                    f"- 根拠状態: {_evidence_status(actor)}",
                    "",
                ]
            )

    lines.extend(["## 4. 見落とされている可能性のある主体", ""])
    affected = data.get("affected_non_parties", [])
    if not affected:
        lines.extend(["- なし、または情報不足", ""])
    else:
        for party in affected:
            lines.extend(
                [
                    f"- **{_text(party.get('name'))}**: {_text(party.get('impact'))}",
                    f"  - 影響経路: {_text(party.get('impact_path'))}",
                    f"  - 状態: `{_text(party.get('status'))}`",
                ]
            )
            for question in party.get("questions", []):
                lines.append(f"  - 追加確認: {_text(question)}")
        lines.append("")

    lines.extend(["## 5. 権利・利益・責任・負担・危険", ""])
    lines.extend(_render_allocations("権利", data.get("rights", [])))
    lines.extend(_render_allocations("利益", data.get("benefits", [])))
    lines.extend(_render_allocations("責任", data.get("responsibilities", [])))
    lines.extend(_render_allocations("負担", data.get("burdens", [])))
    lines.extend(_render_allocations("危険", data.get("risks", [])))

    lines.extend(["## 6. 例外", ""])
    exceptions = data.get("exceptions", [])
    if not exceptions:
        lines.extend(["- なし、または明記なし", ""])
    else:
        for item in exceptions:
            lines.extend(
                [
                    f"- **主体 `{_text(item.get('actor_id'))}`**: {_text(item.get('description'))}",
                    f"  - 提示された根拠: {_text(item.get('stated_rationale'))}",
                    f"  - 範囲／期間: {_text(item.get('scope'))} / {_text(item.get('duration'))}",
                    f"  - 承認者／監督者: {_text(item.get('authorized_by'))} / {_text(item.get('reviewed_by'))}",
                ]
            )
        lines.append("")

    lines.extend(["## 7. 可逆性テスト", ""])
    reversibility = data.get("reversibility_test", [])
    if not reversibility:
        lines.extend(["- 実施結果なし、または適用不能", ""])
    else:
        for item in reversibility:
            lines.extend(
                [
                    f"- 交換した役割: {_text(' ↔ '.join(item.get('roles_swapped', [])))}",
                    f"  - 交換後のルール: {_text(item.get('counterfactual_rule'))}",
                    f"  - 結果: `{_text(item.get('result'))}`",
                    f"  - 理由: {_text(item.get('rationale'))}",
                    f"  - 関連する差: {_text('; '.join(item.get('relevant_differences', [])))}",
                ]
            )
        lines.append("")

    lines.extend(["## 8. 問題候補", ""])
    issues = data.get("detected_issues", [])
    for level in ("clear_issue_candidate", "needs_attention", "insufficient_information"):
        lines.extend([f"### {LEVEL_LABELS[level]}", ""])
        selected = [item for item in issues if item.get("display_level") == level]
        if not selected:
            lines.extend(["- 該当なし", ""])
            continue
        for item in selected:
            lines.extend(
                [
                    f"#### {_text(item.get('title'))}",
                    "",
                    f"- 分類: `{_text(item.get('issue_type'))}`",
                    f"- 関係主体: {_text(', '.join(item.get('actor_ids', [])))}",
                    f"- 説明: {_text(item.get('description'))}",
                    f"- 判断理由: {_text(item.get('rationale'))}",
                    f"- 反対方向の解釈: {_text(item.get('counter_interpretation'))}",
                    f"- 確信度: `{_text(item.get('confidence'))}`（公平点ではありません）",
                    "- 改善のための質問:",
                ]
            )
            lines.extend([f"  - {_text(question)}" for question in item.get("questions", [])])
            lines.append("")

    lines.extend(["## 9. 執行・監督・異議申立て", ""])
    for label, key in (("執行", "enforcement"), ("監督", "oversight")):
        item = data[key]
        lines.extend(
            [
                f"### {label}",
                "",
                f"- 定義済み: {_text(item.get('defined'))}",
                f"- 担当主体: {_text(', '.join(item.get('actors', [])))}",
                f"- 基準: {_text(item.get('criteria'))}",
                f"- 手続: {_text(item.get('process'))}",
                f"- 記録: {_text(item.get('recording'))}",
                f"- 理由提示: {_text(item.get('reason_giving'))}",
                f"- 利益相反対策: {_text('; '.join(item.get('conflict_controls', [])))}",
                "",
            ]
        )
    appeals = data["appeals"]
    lines.extend(
        [
            "### 異議申立て",
            "",
            f"- 定義済み: {_text(appeals.get('defined'))}",
            f"- 申立可能主体: {_text(', '.join(appeals.get('eligible_actors', [])))}",
            f"- 判断者: {_text(appeals.get('decision_maker'))}",
            f"- 期限: {_text(appeals.get('deadline'))}",
            f"- 独立性: `{_text(appeals.get('independence'))}`",
            f"- 詳細: {_text(appeals.get('details'))}",
            "",
        ]
    )

    lines.extend(["## 10. 合理的な別解釈", ""])
    alternatives = data.get("alternative_interpretations", [])
    if not alternatives:
        lines.extend(["- なし、または情報不足", ""])
    else:
        for item in alternatives:
            lines.extend(
                [
                    f"- **解釈**: {_text(item.get('interpretation'))}",
                    f"  - 支持材料: {_text('; '.join(item.get('supports', [])))}",
                    f"  - 弱点: {_text('; '.join(item.get('weaknesses', [])))}",
                    f"  - 追加証拠: {_text('; '.join(item.get('evidence_that_would_help', [])))}",
                ]
            )
        lines.append("")

    lines.extend(["## 11. 不足情報と必要な証拠", "", "### 不足情報", ""])
    for item in data.get("missing_information", []):
        lines.extend(
            [
                f"- {_text(item.get('question'))}",
                f"  - 重要な理由: {_text(item.get('why_it_matters'))}",
                f"  - 影響項目: {_text(', '.join(item.get('affected_fields', [])))}",
            ]
        )
    if not data.get("missing_information"):
        lines.append("- 明示なし")
    lines.extend(["", "### 必要な証拠", ""])
    for item in data.get("evidence_needed", []):
        lines.extend(
            [
                f"- {_text(item.get('evidence'))}",
                f"  - 目的: {_text(item.get('purpose'))}",
                f"  - 候補ソース: {_text(item.get('possible_source'))}",
                f"  - 行動前に必須: {_text(item.get('required_before_action'))}",
            ]
        )
    if not data.get("evidence_needed"):
        lines.append("- 明示なし")

    questions: list[str] = []
    for item in issues:
        questions.extend(_text(q) for q in item.get("questions", []))
    for item in reversibility:
        questions.extend(_text(q) for q in item.get("questions", []))
    for item in affected:
        questions.extend(_text(q) for q in item.get("questions", []))
    unique_questions = list(dict.fromkeys(question for question in questions if question))
    lines.extend(["", "## 12. 改善のための質問", ""])
    lines.extend(_bullets(unique_questions, empty="- 追加質問は明示されていません。人間が原文を再確認してください。"))

    lines.extend(
        [
            "",
            "## 13. AIが判断できない部分",
            "",
            "- 事実関係、証拠の真偽、当事者の意図。",
            "- 法域における適法性と法的効力。",
            "- 共同体が採用すべき価値、許容可能な負担、最終的な採否・処罰。",
            f"- AI回答の確信度理由: {_text(confidence.get('rationale'))}",
            "",
            "## 14. 人間確認",
            "",
            "- 人間レビュー必須: **はい**",
            "- 現在の確認状態: `draft`",
            "- `reviewed` は監査報告を確認した事実であり、元の提案を承認した意味ではありません。",
            "",
            "## 15. 免責",
            "",
            _text(data.get("disclaimer")),
            "",
            "この報告だけで採択、拒否、処罰、契約執行を自動化しないでください。",
            "",
        ]
    )
    return "\n".join(lines)


def render_analysis(
    input_path: Path,
    output_path: Path | None = None,
    *,
    force: bool = False,
    acknowledge_review_reset: bool = False,
) -> Path:
    result = validate_analysis(input_path, write_result=True)
    if not result.valid or result.data is None:
        code = result.findings[0].code if result.findings else "validation_failed"
        raise AuditorError("validation_failed", f"JSON検証に失敗しました（{code}）。")

    case_dir = input_path.parent
    destination = output_path or (case_dir / "audit-report-ja.md")
    if destination.parent.resolve() != case_dir.resolve():
        raise AuditorError("report_outside_case", "報告書はケースフォルダ内へ出力してください。")
    if destination.exists() and not force:
        raise AuditorError("report_exists", "報告書が既にあります。再生成には--forceを指定してください。")

    case, state = read_case(case_dir)
    was_reviewed = state.get("review_status") == "reviewed"
    if was_reviewed:
        integrity = review_integrity(case_dir, state)
        if integrity not in {"valid", "legacy_unbound"}:
            raise AuditorError(
                "review_integrity_failed",
                "確認済み報告書とレビュー記録が一致しません。再生成前に人間が状態を確認してください。",
            )
        if not acknowledge_review_reset:
            raise AuditorError(
                "reviewed_report_requires_acknowledgement",
                "この監査報告書はreviewedです。再生成すると現在の人間確認はdraftへ戻ります。"
                "続行するには--acknowledge-review-resetを指定してください。",
            )

    markdown = render_markdown(
        result.data,
        case_id=result.case_id,
        proposal_sha256=result.proposal_sha256,
    )
    archive = _archive_review_context(case_dir, state)
    try:
        atomic_write_text(destination, markdown)
    except Exception:
        _discard_failed_archive(archive)
        raise

    update_state(
        case_dir,
        state,
        report_status="generated",
        report_file=destination.name,
        report_sha256=sha256_file(destination),
        review_status="draft",
    )
    if archive is not None:
        (case_dir / "review.json").unlink(missing_ok=True)
        append_event(
            case_dir,
            case_id=case["case_id"],
            proposal_sha256=case["proposal_sha256"],
            event="review_archived",
            state="draft",
        )
    append_event(
        case_dir,
        case_id=case["case_id"],
        proposal_sha256=case["proposal_sha256"],
        event="render",
        state="generated",
    )
    return destination
