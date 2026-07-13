"""Disk cache for LLM responses, keyed on model + prompt + generation params."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Optional


class ResponseCache:
    def __init__(self, directory: str | Path = ".cache") -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def key(payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _path(self, key: str) -> Path:
        return self.directory / f"{key}.json"

    def get(self, key: str) -> Optional[dict[str, Any]]:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def put(self, key: str, value: dict[str, Any]) -> None:
        with open(self._path(key), "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False)
