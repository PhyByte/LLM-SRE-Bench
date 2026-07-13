"""Pydantic schemas for validating structured LLM answers, per category."""

from __future__ import annotations

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


class JudgeResult(BaseModel):
    score: float = Field(ge=0, le=10)
    reasoning: str = ""


RESULT_SCHEMAS: dict[str, type[BaseModel]] = {
    "log_parsing": LogParsingResult,
    "anomaly_detection": AnomalyDetectionResult,
    "pattern_correlation": PatternCorrelationResult,
    "metrics_timeseries": TimeSeriesResult,
    "root_cause": RootCauseResult,
}
