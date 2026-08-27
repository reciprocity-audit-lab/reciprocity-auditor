from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .errors import AuditorError


MAX_INPUT_BYTES = 1_048_576
CASE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")

SENSITIVE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private_key_material", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.IGNORECASE)),
    ("openai_key_material", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")),
    ("assigned_secret", re.compile(r"\b(?:api[_-]?key|private[_-]?key|seed[_-]?phrase|password)\s*[:=]\s*[^\s]{8,}", re.IGNORECASE)),
    ("email_address", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("windows_profile_path", re.compile(r"\b[A-Za-z]:\\Users\\[^\\\r\n]+", re.IGNORECASE)),
    ("public_did_requires_approval", re.compile(r"\bdid:key:z6Mk[1-9A-HJ-NP-Za-km-z]{20,}\b")),
)

UNTRUSTED_FLAGS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("instruction_override", re.compile(r"(?:前|以前|上記|これまで).{0,12}(?:命令|指示).{0,8}(?:無視|忘れ)", re.IGNORECASE)),
    ("secret_access_request", re.compile(r"(?:秘密鍵|seed|シード|APIキー|password|パスワード).{0,12}(?:読|表示|送|取得)", re.IGNORECASE)),
    ("external_action_request", re.compile(r"(?:URL|外部|Technocore|GitHub|X).{0,16}(?:投稿|送信|書き込|接続|push)", re.IGNORECASE)),
    ("url_present", re.compile(r"https?://", re.IGNORECASE)),
    ("role_override", re.compile(r"(?:system|developer|assistant)\s*:", re.IGNORECASE)),
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65_536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_limited_bytes(path: Path) -> bytes:
    try:
        size = path.stat().st_size
    except FileNotFoundError as exc:
        raise AuditorError("input_not_found", "入力ファイルが見つかりません。") from exc
    if not path.is_file():
        raise AuditorError("input_not_file", "入力は通常ファイルである必要があります。")
    if size == 0:
        raise AuditorError("input_empty", "入力ファイルが空です。")
    if size > MAX_INPUT_BYTES:
        raise AuditorError("input_too_large", "入力ファイルは1 MiB以下にしてください。")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise AuditorError("input_read_failed", "入力ファイルを読み取れませんでした。") from exc


def decode_utf8(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AuditorError("input_not_utf8", "入力ファイルはUTF-8で保存してください。") from exc


def sensitive_categories(text: str) -> list[str]:
    return [name for name, pattern in SENSITIVE_PATTERNS if pattern.search(text)]


def untrusted_flags(text: str) -> list[str]:
    return [name for name, pattern in UNTRUSTED_FLAGS if pattern.search(text)]


def validate_case_id(case_id: str) -> str:
    if not CASE_ID_PATTERN.fullmatch(case_id):
        raise AuditorError(
            "invalid_case_id",
            "ケースIDは英小文字で始まる64文字以内の英小文字・数字・ハイフン・下線にしてください。",
        )
    return case_id


def load_json(path: Path) -> Any:
    data = read_limited_bytes(path)
    text = decode_utf8(data)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise AuditorError("invalid_json", "JSON構文が正しくありません。") from exc


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def write_new_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(data)
    except FileExistsError as exc:
        raise AuditorError("output_exists", "既存ファイルは上書きしません。") from exc


def write_new_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
    except FileExistsError as exc:
        raise AuditorError("output_exists", "既存ファイルは上書きしません。") from exc


def read_case(case_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    case_value = load_json(case_dir / "case.json")
    state_value = load_json(case_dir / "state.json")
    if not isinstance(case_value, dict) or not isinstance(state_value, dict):
        raise AuditorError("invalid_case_files", "ケース管理ファイルが正しくありません。")
    return case_value, state_value


def update_state(case_dir: Path, state: dict[str, Any], **changes: Any) -> dict[str, Any]:
    updated = dict(state)
    updated.update(changes)
    updated["updated_at"] = utc_now()
    atomic_write_json(case_dir / "state.json", updated)
    return updated


def append_event(
    case_dir: Path,
    *,
    case_id: str,
    proposal_sha256: str,
    event: str,
    state: str,
    error_code: str | None = None,
) -> None:
    record: dict[str, Any] = {
        "at": utc_now(),
        "case_id": case_id,
        "proposal_sha256": proposal_sha256,
        "event": event,
        "state": state,
    }
    if error_code is not None:
        record["error_code"] = error_code
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    with (case_dir / "events.jsonl").open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(line)
