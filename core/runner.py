"""Benchmark orchestration: run every model x category x case x run."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from evaluators.base import get_evaluator
from evaluators.root_cause import evaluate as evaluate_root_cause

from .cache import ResponseCache
from .clients import BaseClient, LLMResponse, RefusalError, build_client
from .config import BenchmarkConfig, ModelConfig
from .lmstudio_host import LMStudioError, ensure_loaded
from .prompts import (
    CODE_GENERATION_SYSTEM_PROMPT,
    CODE_REVIEW_SYSTEM_PROMPT,
    CODE_WRITING_CATEGORIES,
    JUDGE_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    build_judge_prompt,
    build_prompt,
)
from .schemas import RESULT_SCHEMAS
from .utils import extract_json

# Refusals used to be stored as errors; recognise those older records on load.
_LEGACY_REFUSAL = re.compile(r"refused the request|declined the prompt", re.IGNORECASE)
_LEGACY_REFUSAL_CATEGORY = re.compile(r"category=([\w-]+)")


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
    # Set to the classifier category (e.g. "cyber") when the model declined the
    # prompt. A refusal is a completed run scoring 0, not an error: the model
    # was asked and chose not to answer.
    refused: Optional[str] = None

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
            "refused": self.refused,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunRecord":
        error = data.get("error")
        refused = data.get("refused")
        if refused is None and error and _LEGACY_REFUSAL.search(error):
            # Written before refusals became a scored outcome. Upgrade in place
            # so old results aren't re-called as if they had failed.
            category = _LEGACY_REFUSAL_CATEGORY.search(error)
            refused = category.group(1) if category else "unspecified"
            error = None
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
            error=error,
            refused=refused,
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

    def _cache_payload(
        self,
        model: ModelConfig,
        system: str,
        user: str,
        run_index: int,
        max_tokens: int,
    ) -> dict:
        return {
            "model": model.name,
            "model_id": model.model_id,
            "provider": model.provider,
            "system": system,
            "user": user,
            "temperature": self.config.temperature,
            "max_tokens": max_tokens,
            "reasoning_effort": model.reasoning_effort,
            "run_index": run_index,
        }

    def _call(
        self,
        model: ModelConfig,
        system: str,
        user: str,
        run_index: int,
        *,
        bypass_cache: bool = False,
    ) -> LLMResponse:
        effective_max = model.max_tokens or self.config.max_tokens
        cache_key = None
        if self.cache is not None:
            cache_key = ResponseCache.key(
                self._cache_payload(model, system, user, run_index, effective_max)
            )
            if not bypass_cache:
                hit = self.cache.get(cache_key)
                # Fallback: entries written before the key used the per-model
                # max_tokens override still live under the global budget.
                legacy_key = None
                if hit is None and effective_max != self.config.max_tokens:
                    legacy_key = ResponseCache.key(
                        self._cache_payload(
                            model, system, user, run_index, self.config.max_tokens
                        )
                    )
                    hit = self.cache.get(legacy_key)
                    if hit is not None:
                        cache_key = legacy_key
                if hit is not None:
                    return LLMResponse(
                        text=hit["text"],
                        latency_s=hit["latency_s"],
                        input_tokens=hit.get("input_tokens"),
                        output_tokens=hit.get("output_tokens"),
                        cached=True,
                        cache_key=cache_key,
                    )

        response = self._client(model).complete(system, user)
        # Do not put here: malformed / unparseable answers must not poison
        # retries. _run_one caches only after a successful parse + score.
        return LLMResponse(
            text=response.text,
            latency_s=response.latency_s,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cached=False,
            cache_key=cache_key,
        )
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
        *,
        bypass_cache: bool = False,
    ) -> RunRecord:
        record = RunRecord(
            model=model.name, category=category, case_id=case["id"], run_index=run_index, score=0.0
        )
        response: Optional[LLMResponse] = None
        try:
            user_prompt = build_prompt(category, case)
            if category in CODE_WRITING_CATEGORIES:
                system_prompt = CODE_GENERATION_SYSTEM_PROMPT
            elif category == "code_review":
                system_prompt = CODE_REVIEW_SYSTEM_PROMPT
            else:
                system_prompt = SYSTEM_PROMPT
            response = self._call(
                model, system_prompt, user_prompt, run_index, bypass_cache=bypass_cache
            )
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
            # Cache only answers that parsed and scored — a broken JSON blob
            # must not be replayed forever on --retries / re-runs.
            if (
                self.cache is not None
                and not response.cached
                and response.cache_key
            ):
                self.cache.put(
                    response.cache_key,
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
        except RefusalError as exc:
            # A completed run the model declined to answer: scores 0 like any
            # other wrong answer, and never counts as a failure of the harness.
            record.refused = exc.category
            record.latency_s = 0.0
        except Exception as exc:  # noqa: BLE001 — one bad call must never kill the run
            # Poisoned cache: same unparseable text would fail every retry.
            # Drop it and take one live shot before recording the error.
            if (
                not bypass_cache
                and record.cached
                and self.cache is not None
                and response is not None
                and response.cache_key
            ):
                self.cache.delete(response.cache_key)
                return self._run_one(
                    model, category, case, run_index, judge, bypass_cache=True
                )
            record.error = f"{type(exc).__name__}: {exc}"
        return record

    # Errors worth re-attempting on a retry pass: transient conditions that may
    # succeed next time (intermittent 401, rate limits/5xx that outlasted the
    # per-call backoff, timeouts, malformed JSON). Clearly-permanent errors
    # (403 no-access, 404, connection refused) and circuit-breaker skips are
    # NOT retried — that would just burn calls against a dead model.
    _PERMANENT_ERROR_MARKERS = (
        "skipped:",
        "http 400",
        "http 403",
        "http 404",
        "permission-denied",
        "cannot connect",
        "could not be loaded",
        "is not available",
        "unsupported provider",
        # Same prompt + same max_tokens → same empty-at-length outcome. Retrying
        # just regenerates thousands of thinking tokens for minutes per slot.
        "finish_reason=length",
        "reasoning consumed the budget",
        "thinking consumed the budget",
    )

    # Per-prompt verdicts: the endpoint is healthy, this case failed. Do not
    # count them toward the consecutive-failure circuit breaker.
    _PER_PROMPT_ERROR_MARKERS = (
        "empty response",
        "validationerror",
        "jsondecodeerror",
        "expecting value",
        "no json",
    )

    @classmethod
    def _is_retryable_error(cls, error: Optional[str]) -> bool:
        if not error:
            return False
        lowered = error.lower()
        return not any(marker in lowered for marker in cls._PERMANENT_ERROR_MARKERS)

    @classmethod
    def _is_per_prompt_error(cls, error: Optional[str]) -> bool:
        if not error:
            return False
        lowered = error.lower()
        return any(marker in lowered for marker in cls._PER_PROMPT_ERROR_MARKERS)

    def run(
        self,
        datasets: dict[str, list[dict[str, Any]]],
        model_names: Optional[list[str]] = None,
        on_record: Optional[Callable[[RunRecord], None]] = None,
        retry_failed: int = 0,
        skip_keys: Optional[set[tuple[str, str, str, int]]] = None,
        on_model_complete: Optional[Callable[[str, list[RunRecord], float], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
    ) -> tuple[list[RunRecord], dict[str, float]]:
        """Run the benchmark.

        Args:
            retry_failed: per slot, how many extra attempts after a transient
                failure (timeout, bad JSON, empty response, …). Retries run
                immediately on that slot before moving on, so the progress bar
                keeps advancing instead of stalling in a bulk retry pass at
                the end of the model. 0 disables.
            skip_keys: ``(model, category, case_id, run_index)`` slots to leave
                untouched (already-successful results). They are not called
                and not emitted — merge keeps the stored record.
            on_model_complete: called with (model name, its records, elapsed
                seconds) as soon as each model finishes, so callers can persist
                it. Without this a long multi-model run keeps everything in
                memory and one Ctrl-C throws away every finished model.
            on_status: called with progress lines for out-of-band work, such as
                swapping models in and out of an LM Studio host, and for
                in-progress retry attempts before a slot's final outcome.

        Returns:
            (records, model_durations)
            model_durations maps model name -> wall-clock seconds spent on that model's full set.
        """
        models = [
            m for m in self.config.models if model_names is None or m.name in model_names
        ]
        records: list[RunRecord] = []
        model_durations: dict[str, float] = {}
        skip = skip_keys or set()

        for model in models:
            model_start = time.perf_counter()
            model_records: list[RunRecord] = []
            consecutive_failures = 0
            try:
                ensure_loaded(model, log=on_status)
            except LMStudioError as exc:
                # Falling through would benchmark whichever model happens to be
                # resident and file the scores under this one's name, so fail
                # every slot with the real reason instead.
                circuit_error = f"{model.model_id} could not be loaded — {exc}"
            else:
                circuit_error = None
            for category, cases in datasets.items():
                for case in cases:
                    judge = self._make_judge(case) if category == "root_cause" else None
                    for run_index in range(self.config.runs_per_test):
                        if (model.name, category, case["id"], run_index) in skip:
                            continue
                        if circuit_error is not None:
                            record = RunRecord(
                                model=model.name,
                                category=category,
                                case_id=case["id"],
                                run_index=run_index,
                                score=0.0,
                                error=circuit_error,
                            )
                        else:
                            label = (
                                f"{model.name} · {category} · {case['id']} "
                                f"#{run_index}"
                            )
                            if on_status is not None:
                                on_status(f"{label} …")
                            record = self._run_one(
                                model, category, case, run_index, judge
                            )
                            # Immediate per-slot retries: finish this case before
                            # moving on so the progress counter never sits idle
                            # while a bulk end-of-model retry pass runs.
                            for attempt in range(1, retry_failed + 1):
                                if not self._is_retryable_error(record.error):
                                    break
                                if on_status is not None:
                                    on_status(
                                        f"{label} → ERR, retry "
                                        f"{attempt}/{retry_failed} …"
                                    )
                                record = self._run_one(
                                    model,
                                    category,
                                    case,
                                    run_index,
                                    judge,
                                    bypass_cache=True,
                                )
                            # Circuit breaker counts the slot once (final outcome),
                            # not each intermediate attempt.
                            if (
                                record.error is None
                                or self._is_per_prompt_error(record.error)
                            ):
                                # Success, or a case-specific miss (refusal / bad
                                # JSON / empty answer). The endpoint is fine.
                                consecutive_failures = 0
                            else:
                                consecutive_failures += 1
                                if consecutive_failures >= self.CIRCUIT_BREAKER_THRESHOLD:
                                    circuit_error = (
                                        f"skipped: {self.CIRCUIT_BREAKER_THRESHOLD} "
                                        "consecutive failures for this model (bad key, "
                                        "unreachable endpoint, or exhausted quota)"
                                    )
                        model_records.append(record)
                        if on_record is not None:
                            on_record(record)

            records.extend(model_records)
            model_durations[model.name] = time.perf_counter() - model_start
            if on_model_complete is not None:
                on_model_complete(model.name, model_records, model_durations[model.name])

        return records, model_durations

    @staticmethod
    def total_tasks(
        config: BenchmarkConfig,
        datasets: dict[str, list[dict[str, Any]]],
        model_names: Optional[list[str]] = None,
        skip_keys: Optional[set[tuple[str, str, str, int]]] = None,
    ) -> int:
        models = [
            m for m in config.models if model_names is None or m.name in model_names
        ]
        skip = skip_keys or set()
        if not skip:
            n_cases = sum(len(cases) for cases in datasets.values())
            return len(models) * n_cases * config.runs_per_test
        count = 0
        for model in models:
            for category, cases in datasets.items():
                for case in cases:
                    for run_index in range(config.runs_per_test):
                        if (model.name, category, case["id"], run_index) not in skip:
                            count += 1
        return count
