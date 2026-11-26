"""Reference search: which settings refer to a given entity?"""
from __future__ import annotations

import glob
import os
import re
from typing import Any


MAX_FILE_BYTES = 20 * 1024 * 1024  # これより大きいファイルは、検索の対象にしない


def _read(path: str) -> str:
    try:
        if os.path.getsize(path) > MAX_FILE_BYTES:
            return ""
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return ""


def _excerpt(line: str, match: re.Match[str], width: int = 50) -> str:
    """一致した箇所の前後だけを返す(1行が長いデータでも、無関係な内容を表示しない)。"""
    start = max(0, match.start() - width)
    end = min(len(line), match.end() + width)
    text = line[start:end].strip()
    return ("…" if start > 0 else "") + text + ("…" if end < len(line) else "")


def search_references(config_dir: str, entity_id: str) -> list[dict[str, Any]]:
    """entity_id を参照している設定の箇所を探す(YAML・ダッシュボードの保存データ)。"""
    pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(entity_id)}(?![A-Za-z0-9_])")
    files = [
        os.path.join(config_dir, name)
        for name in ("automations.yaml", "scenes.yaml", "scripts.yaml", "configuration.yaml")
    ]
    files += sorted(glob.glob(os.path.join(config_dir, ".storage", "lovelace*")))
    refs: list[dict[str, Any]] = []
    for path in files:
        text = _read(path)
        if not text:
            continue
        for i, line in enumerate(text.splitlines()):
            match = pattern.search(line)
            if match:
                refs.append(
                    {
                        "file": os.path.relpath(path, config_dir),
                        "line": i + 1,
                        "text": _excerpt(line, match),
                    }
                )
    return refs

