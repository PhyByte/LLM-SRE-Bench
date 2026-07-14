"""Disk cache for LLM responses, keyed on model + prompt + generation params.

Supports selective clearing by model.
"""

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
                data = json.load(f)
            # Strip internal metadata if present
            if isinstance(data, dict) and "_meta" in data:
                data = {k: v for k, v in data.items() if k != "_meta"}
            return data
        except (json.JSONDecodeError, OSError):
            return None

    def put(self, key: str, value: dict[str, Any], meta: dict[str, Any] | None = None) -> None:
        """Store a value. If meta is provided, it is stored under _meta for selective clearing."""
        data = dict(value)  # copy
        if meta:
            data["_meta"] = meta
        with open(self._path(key), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def clear_model(self, model_name: str) -> int:
        """Delete all cached entries that belong to the given model name.

        Returns the number of files deleted.
        """
        deleted = 0
        if not self.directory.exists():
            return 0

        for path in list(self.directory.glob("*.json")):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                meta = data.get("_meta", {}) if isinstance(data, dict) else {}
                if meta.get("model") == model_name:
                    path.unlink(missing_ok=True)
                    deleted += 1
            except (json.JSONDecodeError, OSError):
                # Skip unreadable files
                continue
        return deleted

    def clear_all(self) -> int:
        """Delete the entire cache directory contents. Returns number of files removed."""
        deleted = 0
        if not self.directory.exists():
            return 0
        for path in list(self.directory.glob("*.json")):
            try:
                path.unlink(missing_ok=True)
                deleted += 1
            except OSError:
                pass
        return deleted
