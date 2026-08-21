"""Pydantic schemas for validating structured LLM answers, per category."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LogParsingResult(BaseModel):
    templates: list[str]


class AnomalyDetectionResult(BaseModel):
    anomalous_indices: list[int]


class Pattern(BaseModel):
    name: str
    description: str = ""


class Correlation(BaseModel):
    cause: str
    effect: str


class PatternCorrelationResult(BaseModel):
    patterns: list[Pattern]
    correlations: list[Correlation] = Field(default_factory=list)


class TimeSeriesResult(BaseModel):
    anomalous_indices: list[int]


class RootCauseResult(BaseModel):
    root_cause: str
    summary: str


class Evidence(BaseModel):
    """One observation, tied to the modality it was read from.

    The modality is constrained so a model can't dodge the grounding score by
    inventing a source; anything outside the three bundled modalities is a
    validation failure, same as any other malformed answer.
    """

    modality: Literal["metrics", "logs", "traces"]
    observation: str


class MultiModalRCAResult(BaseModel):
    culprit_service: str
    fault_type: str  # closed vocabulary, listed in the prompt
    evidence: list[Evidence] = Field(default_factory=list)
    summary: str = ""


class JudgeResult(BaseModel):
    score: float = Field(ge=0, le=10)
    reasoning: str = ""


class CodeGenerationResult(BaseModel):
    code: str


RESULT_SCHEMAS: dict[str, type[BaseModel]] = {
    "log_parsing": LogParsingResult,
    "anomaly_detection": AnomalyDetectionResult,
    "pattern_correlation": PatternCorrelationResult,
    "metrics_timeseries": TimeSeriesResult,
    "root_cause": RootCauseResult,
    "multimodal_rca": MultiModalRCAResult,
    "code_generation": CodeGenerationResult,
}
