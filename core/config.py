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

Provider = Literal["openai", "xai", "anthropic", "google", "ollama", "mock"]

# SRE/observability track weights (original, must sum to 1.0)
SRE_CATEGORY_WEIGHTS: dict[str, float] = {
    "log_parsing": 0.15,
    "anomaly_detection": 0.25,
    "pattern_correlation": 0.15,
    "metrics_timeseries": 0.10,
    "root_cause": 0.10,
    "multimodal_rca": 0.20,
    "efficiency": 0.05,
}

# Developer track: equal weight per language (95% total) + efficiency (5%).
# Keys are synthetic score buckets derived from code_generation case_ids.
CODE_GEN_LANGUAGES = ("python", "typescript", "go", "rust")
_CODE_GEN_LANG_WEIGHT = 0.95 / len(CODE_GEN_LANGUAGES)
CODE_GEN_CATEGORY_WEIGHTS: dict[str, float] = {
    **{f"code_gen_{lang}": _CODE_GEN_LANG_WEIGHT for lang in CODE_GEN_LANGUAGES},
    "efficiency": 0.05,
}

# Category weights used for scoring (defaults to SRE track)
# Will be switched based on --suite CLI flag
CATEGORY_WEIGHTS: dict[str, float] = SRE_CATEGORY_WEIGHTS.copy()

# Categories backed by datasets (efficiency is derived from the other runs).
# This includes both SRE and developer categories
SRE_CATEGORIES = [c for c in SRE_CATEGORY_WEIGHTS if c != "efficiency"]
DEVELOPER_CATEGORIES = ["code_generation"]
TASK_CATEGORIES = SRE_CATEGORIES  # Default to SRE for backward compatibility
ALL_CATEGORIES = list(set(SRE_CATEGORIES + DEVELOPER_CATEGORIES))

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
    # LM Studio only. Set this and the runner loads model_id onto the server at
    # base_url with this context before the model's first call, unloading
    # whatever else is resident — so a sweep of local models doesn't need you
    # loading each one by hand in the GUI. Left unset, the model is assumed to
    # be loaded already and LM Studio's saved default context applies, which is
    # usually too small for this benchmark's prompts.
    context_length: Optional[int] = Field(default=None, gt=0)
    # Fraction of the model to offload to GPU (0-1) when auto-loading. Omit to
    # let LM Studio decide.
    gpu_ratio: Optional[float] = Field(default=None, ge=0, le=1)
    # Force JSON output via response_format (OpenAI-compatible + Ollama). Helps
    # weaker models that otherwise reply with prose. Off by default so the
    # benchmark measures unprompted JSON discipline unless you opt in.
    json_mode: bool = False
    # Internal-reasoning effort for models that support it. Omit to use the
    # provider's default. Define two entries with the same model_id but different
    # names/efforts to A/B "with vs. without" heavy reasoning. Wiring per provider:
    #   - openai / xai: sent as `reasoning_effort` on /chat/completions
    #     (OpenAI GPT-5/o-series, xAI Grok models that accept it; LM Studio Qwen
    #     accepts "none" to disable thinking and avoid empty finish_reason=length).
    #   - anthropic: sent as `output_config.effort` (Claude models — Fable 5,
    #     Opus 5/4.8, Sonnet 5, etc. — where thinking is always on and effort is
    #     the depth control). "minimal"/"none" are not valid here; use "low".
    #   - ollama: ignored.
    reasoning_effort: Optional[str] = None
    # Price in USD per 1,000,000 tokens, used to compute a total cost column in
    # the reports. Both must be set for a model to be costed; leave unset for
    # models you don't want priced (they show "—"). Self-hosted/local models can
    # be set to 0 to appear as free.
    price_input: Optional[float] = Field(default=None, ge=0)
    price_output: Optional[float] = Field(default=None, ge=0)

    @field_validator("reasoning_effort")
    @classmethod
    def _check_effort(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        # Union across providers: none (LM Studio / Qwen — disable thinking) +
        # minimal (OpenAI) + low/medium/high (all) + xhigh/max (Anthropic, newer).
        # Provider rejects anything it doesn't take.
        allowed = {"none", "minimal", "low", "medium", "high", "xhigh", "max"}
        if value not in allowed:
            raise ValueError(
                f"reasoning_effort must be one of {sorted(allowed)} or null, got {value!r}"
            )
        return value

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


def set_suite(suite: str) -> list[str]:
    """Set the active suite and return the categories to run.

    Args:
        suite: One of 'sre', 'developer', or 'all'

    Returns:
        List of category names to run

    Note:
        Mutates ``CATEGORY_WEIGHTS`` and ``TASK_CATEGORIES`` in place so every
        module that imported those names keeps seeing the active suite.
    """
    if suite == "sre":
        CATEGORY_WEIGHTS.clear()
        CATEGORY_WEIGHTS.update(SRE_CATEGORY_WEIGHTS)
        TASK_CATEGORIES[:] = list(SRE_CATEGORIES)
        return list(SRE_CATEGORIES)
    if suite == "developer":
        CATEGORY_WEIGHTS.clear()
        CATEGORY_WEIGHTS.update(CODE_GEN_CATEGORY_WEIGHTS)
        TASK_CATEGORIES[:] = list(DEVELOPER_CATEGORIES)
        return list(DEVELOPER_CATEGORIES)
    if suite == "all":
        # Combine both suites with adjusted weights (60% SRE / 40% developer).
        combined: dict[str, float] = {}
        for cat, weight in SRE_CATEGORY_WEIGHTS.items():
            if cat != "efficiency":
                combined[cat] = weight * 0.60
        combined["code_generation"] = 0.40 * 0.95
        combined["efficiency"] = 0.05
        CATEGORY_WEIGHTS.clear()
        CATEGORY_WEIGHTS.update(combined)
        TASK_CATEGORIES[:] = list(SRE_CATEGORIES) + list(DEVELOPER_CATEGORIES)
        return list(TASK_CATEGORIES)
    raise ValueError(f"unknown suite '{suite}', must be 'sre', 'developer', or 'all'")


def detect_suite(categories: set[str]) -> str:
    """Infer which suite fits a set of category names from stored results.

    Returns 'all' when both tracks appear, otherwise the single track that does.
    """
    has_sre = bool(categories & set(SRE_CATEGORIES))
    has_dev = bool(categories & set(DEVELOPER_CATEGORIES))
    if has_sre and has_dev:
        return "all"
    if has_dev:
        return "developer"
    return "sre"
