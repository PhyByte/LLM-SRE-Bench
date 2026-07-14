"""Benchmark orchestration: run every model x category x case x run."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from evaluators.base import get_evaluator
from evaluators.root_cause import evaluate as evaluate_root_cause

from .cache import ResponseCache
from .clients import BaseClient, LLMResponse, build_client
from .config import BenchmarkConfig, ModelConfig
from .prompts import JUDGE_SYSTEM_PROMPT, SYSTEM_PROMPT, build_judge_prompt, build_prompt
from .schemas import RESULT_SCHEMAS
from .utils import extract_json


@dataclass
class RunRecord:
    model: str
    category: str
    case_id: str
    run_index: int
    score: float  # 0-1; 0 when error is set
    metrics: dict[str, float] = field(default_factory=dict)
    latency_s: float = 0.0
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cached: bool = False
    error: Optional[str] = None

    @property
    def total_tokens(self) -> Optional[int]:
        if self.input_tokens is None and self.output_tokens is None:
            return None
        return (self.input_tokens or 0) + (self.output_tokens or 0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "category": self.category,
            "case_id": self.case_id,
            "run_index": self.run_index,
            "score": self.score,
            "metrics": self.metrics,
            "latency_s": self.latency_s,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cached": self.cached,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunRecord":
        return cls(
            model=data["model"],
            category=data["category"],
            case_id=data["case_id"],
            run_index=data["run_index"],
            score=float(data["score"]),
            metrics=dict(data.get("metrics", {})),
            latency_s=float(data.get("latency_s", 0.0)),
            input_tokens=data.get("input_tokens"),
            output_tokens=data.get("output_tokens"),
            cached=bool(data.get("cached", False)),
            error=data.get("error"),
        )


class BenchmarkRunner:
    # After this many consecutive failed calls for a model, its remaining
    # calls are skipped (recorded as errors) instead of retried — keeps a
    # bad key, dead endpoint, or exhausted quota from stalling the run.
    CIRCUIT_BREAKER_THRESHOLD = 5

    def __init__(
        self,
        config: BenchmarkConfig,
        use_cache: bool = True,
        cache_dir: str = ".cache",
    ) -> None:
        self.config = config
        self.cache = ResponseCache(cache_dir) if use_cache else None
        self._clients: dict[str, BaseClient] = {}

    def _client(self, model: ModelConfig) -> BaseClient:
        if model.name not in self._clients:
            self._clients[model.name] = build_client(model, self.config)
        return self._clients[model.name]

    def _call(self, model: ModelConfig, system: str, user: str, run_index: int) -> LLMResponse:
        cache_key = None
        if self.cache is not None:
            cache_key = ResponseCache.key(
                {
                    "model": model.name,
                    "model_id": model.model_id,
                    "provider": model.provider,
                    "system": system,
                    "user": user,
                    "temperature": self.config.temperature,
                    "max_tokens": self.config.max_tokens,
                    "run_index": run_index,
                }
            )
            hit = self.cache.get(cache_key)
            if hit is not None:
                return LLMResponse(
                    text=hit["text"],
                    latency_s=hit["latency_s"],
                    input_tokens=hit.get("input_tokens"),
                    output_tokens=hit.get("output_tokens"),
                    cached=True,
                )

        response = self._client(model).complete(system, user)

        if self.cache is not None and cache_key is not None:
            self.cache.put(
                cache_key,
                {
                    "text": response.text,
                    "latency_s": response.latency_s,
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                },
                meta={
                    "model": model.name,
                    "model_id": model.model_id,
                    "provider": model.provider,
                },
            )
        return response

    def _make_judge(self, case: dict[str, Any]) -> Optional[Callable[[str, str], str]]:
        if self.config.judge_model is None:
            return None
        judge_model = self.config.get_model(self.config.judge_model)

        def judge(root_cause: str, summary: str) -> str:
            prompt = build_judge_prompt(case, root_cause, summary)
            return self._client(judge_model).complete(JUDGE_SYSTEM_PROMPT, prompt).text

        return judge

    def _run_one(
        self,
        model: ModelConfig,
        category: str,
        case: dict[str, Any],
        run_index: int,
        judge: Optional[Callable[[str, str], str]],
    ) -> RunRecord:
        record = RunRecord(
            model=model.name, category=category, case_id=case["id"], run_index=run_index, score=0.0
        )
        try:
            user_prompt = build_prompt(category, case)
            response = self._call(model, SYSTEM_PROMPT, user_prompt, run_index)
            record.latency_s = response.latency_s
            record.input_tokens = response.input_tokens
            record.output_tokens = response.output_tokens
            record.cached = response.cached

            parsed = RESULT_SCHEMAS[category].model_validate(extract_json(response.text))
            if category == "root_cause":
                evaluation = evaluate_root_cause(case, parsed, judge=judge)
            else:
                evaluation = get_evaluator(category)(case, parsed)
            record.score = evaluation.score
            record.metrics = evaluation.metrics
        except Exception as exc:  # noqa: BLE001 — one bad call must never kill the run
            record.error = f"{type(exc).__name__}: {exc}"
        return record

    # Errors worth re-attempting on a retry pass: transient conditions that may
    # succeed next time (intermittent 401, rate limits/5xx that outlasted the
    # per-call backoff, timeouts, malformed JSON). Clearly-permanent errors
    # (403 no-access, 404, connection refused) and circuit-breaker skips are
    # NOT retried — that would just burn calls against a dead model.
    _PERMANENT_ERROR_MARKERS = (
        "skipped:",
        "http 403",
        "http 404",
        "permission-denied",
        "cannot connect",
        "is not available",
        "unsupported provider",
    )

    @classmethod
    def _is_retryable_error(cls, error: Optional[str]) -> bool:
        if not error:
            return False
        lowered = error.lower()
        return not any(marker in lowered for marker in cls._PERMANENT_ERROR_MARKERS)

    def run(
        self,
        datasets: dict[str, list[dict[str, Any]]],
        model_names: Optional[list[str]] = None,
        on_record: Optional[Callable[[RunRecord], None]] = None,
        retry_failed: int = 0,
    ) -> tuple[list[RunRecord], dict[str, float]]:
        """Run the benchmark.

        Args:
            retry_failed: after the initial pass over a model, re-attempt runs
                that failed with a transient error, up to this many extra passes.

        Returns:
            (records, model_durations)
            model_durations maps model name -> wall-clock seconds spent on that model's full set.
        """
        models = [
            m for m in self.config.models if model_names is None or m.name in model_names
        ]
        records: list[RunRecord] = []
        model_durations: dict[str, float] = {}
        case_index = {
            (category, case["id"]): case
            for category, cases in datasets.items()
            for case in cases
        }

        for model in models:
            model_start = time.perf_counter()
            model_records: list[RunRecord] = []
            consecutive_failures = 0
            circuit_open = False
            for category, cases in datasets.items():
                for case in cases:
                    judge = self._make_judge(case) if category == "root_cause" else None
                    for run_index in range(self.config.runs_per_test):
                        if circuit_open:
                            record = RunRecord(
                                model=model.name,
                                category=category,
                                case_id=case["id"],
                                run_index=run_index,
                                score=0.0,
                                error=(
                                    f"skipped: {self.CIRCUIT_BREAKER_THRESHOLD} consecutive "
                                    "failures for this model (bad key, unreachable endpoint, "
                                    "or exhausted quota)"
                                ),
                            )
                        else:
                            record = self._run_one(model, category, case, run_index, judge)
                            if record.error is not None:
                                consecutive_failures += 1
                                if consecutive_failures >= self.CIRCUIT_BREAKER_THRESHOLD:
                                    circuit_open = True
                            else:
                                consecutive_failures = 0
                        model_records.append(record)
                        if on_record is not None:
                            on_record(record)

            # Retry passes: re-attempt only transient failures for this model.
            for _attempt in range(retry_failed):
                retryable = [
                    r for r in model_records if self._is_retryable_error(r.error)
                ]
                if not retryable:
                    break
                for record in retryable:
                    case = case_index[(record.category, record.case_id)]
                    judge = (
                        self._make_judge(case) if record.category == "root_cause" else None
                    )
                    fresh = self._run_one(
                        model, record.category, case, record.run_index, judge
                    )
                    # Replace the failed record in place with the new attempt.
                    record.score = fresh.score
                    record.metrics = fresh.metrics
                    record.latency_s = fresh.latency_s
                    record.input_tokens = fresh.input_tokens
                    record.output_tokens = fresh.output_tokens
                    record.cached = fresh.cached
                    record.error = fresh.error
                    if on_record is not None:
                        on_record(record)

            records.extend(model_records)
            model_durations[model.name] = time.perf_counter() - model_start

        return records, model_durations

    @staticmethod
    def total_tasks(
        config: BenchmarkConfig,
        datasets: dict[str, list[dict[str, Any]]],
        model_names: Optional[list[str]] = None,
    ) -> int:
        n_models = len(
            [m for m in config.models if model_names is None or m.name in model_names]
        )
        n_cases = sum(len(cases) for cases in datasets.values())
        return n_models * n_cases * config.runs_per_test
