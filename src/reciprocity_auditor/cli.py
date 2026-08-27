from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path

from .errors import AuditorError
from .io_utils import project_root
from .packet import prepare_case
from .publication import export_public_case
from .rendering import render_analysis
from .validation import validate_analysis
from .workflow import REVIEW_STATES, case_status, record_review


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reciprocity-auditor",
        description="外部通信を行わない相互性監査の手動受け渡しMVP",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare", help="未信頼の提案から分析パケットを作成")
    prepare.add_argument("--input", type=Path, required=True, help="UTF-8提案ファイル")
    prepare.add_argument("--output", type=Path, required=True, help="新規ケースフォルダ")
    prepare.add_argument("--case-id", help="省略時は出力フォルダ名")

    validate = commands.add_parser("validate", help="手動保存したAI回答JSONを検証")
    validate.add_argument("--input", type=Path, required=True, help="ケース内のanalysis.json")

    render = commands.add_parser("render", help="検証済みJSONを日本語Markdownへ変換")
    render.add_argument("--input", type=Path, required=True, help="ケース内のanalysis.json")
    render.add_argument("--output", type=Path, help="ケース内の出力ファイル")
    render.add_argument("--force", action="store_true", help="既存報告書を意図的に再生成")

    review = commands.add_parser("review", help="監査報告の人間確認状態を記録")
    review.add_argument("--case", type=Path, required=True, help="ケースフォルダ")
    review.add_argument("--state", choices=sorted(REVIEW_STATES), required=True)
    review.add_argument("--reviewer-label", help="実名不要の匿名ラベル")
    review.add_argument("--note", help="任意の短いレビューメモ。秘密情報は禁止")

    status = commands.add_parser("status", help="ケース状態を機微情報なしで表示")
    status.add_argument("--case", type=Path, required=True, help="ケースフォルダ")

    export_public = commands.add_parser("export-public", help="レビュー済みケースの公開用コピーを安全に作成")
    export_public.add_argument("--case", type=Path, required=True, help="レビュー済みケースフォルダ")
    export_public.add_argument("--output", type=Path, required=True, help="新規公開用フォルダ")
    export_public.add_argument("--zip", type=Path, help="任意の決定的ZIP出力先")

    commands.add_parser("test", help="ローカルunittestを実行")
    return parser


def _run_tests() -> int:
    root = project_root()
    suite = unittest.defaultTestLoader.discover(
        str(root / "tests"),
        pattern="test*.py",
        top_level_dir=str(root),
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            result = prepare_case(args.input, args.output, requested_case_id=args.case_id)
            print("prepare: 完了")
            print(f"case_id: {result['case_id']}")
            print(f"proposal_sha256: {result['proposal_sha256']}")
            print("state: AI回答待ち")
            if result["flags"]:
                print("notice: 未信頼入力の注意フラグを記録しました。内容は実行していません。")
            return 0

        if args.command == "validate":
            result = validate_analysis(args.input, write_result=True)
            if result.valid:
                print("validate: 合格")
                print(f"case_id: {result.case_id}")
                print("state: JSON検証済み")
                return 0
            print("validate: 不合格", file=sys.stderr)
            for finding in result.findings:
                print(f"ERROR [{finding.code}] {finding.path}: {finding.message}", file=sys.stderr)
            return 2

        if args.command == "render":
            destination = render_analysis(args.input, args.output, force=args.force)
            print("render: 完了")
            print(f"output: {destination.name}")
            print("state: 人間確認待ち")
            return 0

        if args.command == "review":
            record = record_review(
                args.case,
                args.state,
                reviewer_label=args.reviewer_label,
                note=args.note,
            )
            print("review: 記録完了")
            print(f"case_id: {record['case_id']}")
            print(f"state: {record['review_state']}")
            print("meaning: 監査報告の確認記録であり、元提案の承認ではありません。")
            return 0

        if args.command == "status":
            status_value = case_status(args.case)
            print(f"case_id: {status_value['case_id']}")
            print(f"proposal_sha256: {status_value['proposal_sha256']}")
            print(f"prepare: {status_value['prepare']}")
            print(f"AI回答: {status_value['analysis']}")
            print(f"JSON検証: {status_value['validation']}")
            print(f"報告書: {status_value['report']}")
            print(f"人間確認: {status_value['human_review']}")
            print(f"現在状態: {status_value['current']}")
            return 0

        if args.command == "export-public":
            result = export_public_case(args.case, args.output, zip_path=args.zip)
            print("export-public: 完了")
            print(f"case_id: {result.case_id}")
            print(f"output: {result.output_dir.name}")
            print(f"files: {result.file_count}")
            print("privacy_scan: pass")
            print("timestamps: normalized")
            if result.zip_path is not None:
                print(f"zip: {result.zip_path.name}")
                print(f"zip_sha256: {result.zip_sha256}")
            return 0

        if args.command == "test":
            return _run_tests()
        parser.error("不明なコマンドです。")
    except AuditorError as exc:
        print(f"ERROR [{exc.code}]: {exc.message}", file=sys.stderr)
        return exc.exit_code
    return 2
