"""Benchmark configuration loading and validation."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Literal, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator, model_validator

load_dotenv()

Provider = Literal["openai", "xai", "anthropic", "ollama", "mock"]

# Category name -> weight in the global score. Must sum to 1.0.
CATEGORY_WEIGHTS: dict[str, float] = {
    "log_parsing": 0.20,
    "anomaly_detection": 0.30,
    "pattern_correlation": 0.20,
    "metrics_timeseries": 0.15,
    "root_cause": 0.10,
    "efficiency": 0.05,
}

# Categories backed by datasets (efficiency is derived from the other runs).
TASK_CATEGORIES = [c for c in CATEGORY_WEIGHTS if c != "efficiency"]

_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class ModelConfig(BaseModel):
    name: str
    provider: Provider
    model_id: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    # Per-model overrides of the global settings. Handy for slow local models
    # (e.g. a 70B in LM Studio needs a much longer timeout than a cloud API).
    request_timeout: Optional[float] = None
    max_tokens: Optional[int] = None
    # Force JSON output via response_format (OpenAI-compatible + Ollama). Helps
    # weaker models that otherwise reply with prose. Off by default so the
    # benchmark measures unprompted JSON discipline unless you opt in.
    json_mode: bool = False

    @field_validator("api_key")
    @classmethod
    def _expand_env(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        expanded = _ENV_PATTERN.sub(lambda m: os.environ.get(m.group(1), ""), value)
        return expanded or None


class BenchmarkConfig(BaseModel):
    runs_per_test: int = Field(default=3, ge=1)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=64)
    request_timeout: float = Field(default=120.0, gt=0)
    judge_model: Optional[str] = None
    models: list[ModelConfig]

    @model_validator(mode="after")
    def _validate_judge(self) -> "BenchmarkConfig":
        if self.judge_model is not None:
            names = {m.name for m in self.models}
            if self.judge_model not in names:
                raise ValueError(
                    f"judge_model '{self.judge_model}' is not defined in models: {sorted(names)}"
                )
        return self

    @classmethod
    def load(cls, path: str | Path) -> "BenchmarkConfig":
        with open(path, encoding="utf-8") as f:
            return cls.model_validate(json.load(f))

    def get_model(self, name: str) -> ModelConfig:
        for m in self.models:
            if m.name == name:
                return m
        raise KeyError(f"unknown model '{name}'")
