"""LLM provider clients.

- OpenAI-compatible endpoints (OpenAI, xAI, and anything speaking
  /chat/completions) and Ollama use httpx with retry/backoff.
- Anthropic uses the official `anthropic` SDK (which retries 429/5xx itself).
- The "mock" provider runs fully offline with simple heuristics, useful for
  smoke-testing the pipeline without API keys.
"""

from __future__ import annotations

import json
import random
import re
import statistics
import time
from dataclasses import dataclass
from typing import Optional

import httpx

from .config import BenchmarkConfig, ModelConfig


class ClientError(Exception):
    """A request failed permanently (after retries) or was refused."""


@dataclass
class LLMResponse:
    text: str
    latency_s: float
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cached: bool = False

    @property
    def total_tokens(self) -> Optional[int]:
        if self.input_tokens is None and self.output_tokens is None:
            return None
        return (self.input_tokens or 0) + (self.output_tokens or 0)


class BaseClient:
    def __init__(self, model: ModelConfig, config: BenchmarkConfig) -> None:
        self.model = model
        self.config = config

    def complete(self, system: str, user: str) -> LLMResponse:
        raise NotImplementedError


_RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 529}
_MAX_RETRIES = 4


def _retrying_post(client: httpx.Client, url: str, **kwargs) -> httpx.Response:
    """POST with exponential backoff on rate limits and transient failures."""
    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = client.post(url, **kwargs)
            if response.status_code < 400:
                return response
            if response.status_code not in _RETRYABLE_STATUS:
                raise ClientError(
                    f"HTTP {response.status_code} from {url}: {response.text[:300]}"
                )
            last_error = ClientError(
                f"HTTP {response.status_code} from {url}: {response.text[:300]}"
            )
            retry_after = response.headers.get("retry-after")
            delay = float(retry_after) if retry_after else 2**attempt + random.random()
        except httpx.ConnectError as exc:
            # Endpoint unreachable (e.g. Ollama not running): retrying won't help.
            raise ClientError(f"cannot connect to {url}: {exc}") from exc
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_error = exc
            delay = 2**attempt + random.random()
        if attempt < _MAX_RETRIES:
            time.sleep(min(delay, 60.0))
    raise ClientError(f"request failed after {_MAX_RETRIES + 1} attempts: {last_error}")


class OpenAICompatibleClient(BaseClient):
    """OpenAI, xAI Grok, and any other /chat/completions-compatible endpoint."""

    _DEFAULT_BASE_URLS = {
        "openai": "https://api.openai.com/v1",
        "xai": "https://api.x.ai/v1",
    }

    def __init__(self, model: ModelConfig, config: BenchmarkConfig) -> None:
        super().__init__(model, config)
        base_url = model.base_url or self._DEFAULT_BASE_URLS.get(model.provider)
        if not base_url:
            raise ClientError(f"model '{model.name}' needs a base_url")
        headers = {"Content-Type": "application/json"}
        if model.api_key:
            headers["Authorization"] = f"Bearer {model.api_key}"
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=config.request_timeout,
        )

    def complete(self, system: str, user: str) -> LLMResponse:
        payload = {
            "model": self.model.model_id,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        start = time.perf_counter()
        response = _retrying_post(self._http, "/chat/completions", json=payload)
        latency = time.perf_counter() - start
        data = response.json()
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError) as exc:
            raise ClientError(f"malformed completion response: {data}") from exc
        usage = data.get("usage") or {}
        return LLMResponse(
            text=text,
            latency_s=latency,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
        )


class AnthropicClient(BaseClient):
    def __init__(self, model: ModelConfig, config: BenchmarkConfig) -> None:
        super().__init__(model, config)
        import anthropic

        self._anthropic = anthropic
        self._client = anthropic.Anthropic(
            api_key=model.api_key or None,
            timeout=config.request_timeout,
            max_retries=_MAX_RETRIES,
        )

    def complete(self, system: str, user: str) -> LLMResponse:
        # Sampling params are deliberately omitted: Opus 4.7+ models reject
        # temperature/top_p/top_k with a 400.
        start = time.perf_counter()
        try:
            response = self._client.messages.create(
                model=self.model.model_id,
                max_tokens=self.config.max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except self._anthropic.APIError as exc:
            raise ClientError(f"Anthropic API error: {exc}") from exc
        latency = time.perf_counter() - start
        if response.stop_reason == "refusal":
            raise ClientError("Anthropic model refused the request")
        text = "".join(b.text for b in response.content if b.type == "text")
        return LLMResponse(
            text=text,
            latency_s=latency,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )


class OllamaClient(BaseClient):
    def __init__(self, model: ModelConfig, config: BenchmarkConfig) -> None:
        super().__init__(model, config)
        base_url = (model.base_url or "http://localhost:11434").rstrip("/")
        self._http = httpx.Client(base_url=base_url, timeout=config.request_timeout)

    def complete(self, system: str, user: str) -> LLMResponse:
        payload = {
            "model": self.model.model_id,
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
            },
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        start = time.perf_counter()
        response = _retrying_post(self._http, "/api/chat", json=payload)
        latency = time.perf_counter() - start
        data = response.json()
        text = (data.get("message") or {}).get("content", "")
        return LLMResponse(
            text=text,
            latency_s=latency,
            input_tokens=data.get("prompt_eval_count"),
            output_tokens=data.get("eval_count"),
        )


class MockClient(BaseClient):
    """Offline provider for smoke tests.

    model_id "heuristic" answers with simple rule-based analysis of the prompt;
    model_id "naive" returns schema-valid but low-effort answers. Both let the
    full pipeline (prompting, parsing, scoring, reporting) run without keys.
    """

    _LOGS = re.compile(r"<logs>\n(.*?)\n</logs>", re.DOTALL)
    _SERIES = re.compile(r"<series>\n(.*?)\n</series>", re.DOTALL)
    _ANOMALY_WORDS = ("error", "fatal", "exception", "fail", "denied", "timeout", "panic")
    _VARIABLE = re.compile(
        r"(/[\w./-]+|\b\d+(?:\.\d+)+(?::\d+)?\b|\b0x[0-9a-fA-F]+\b|\b\w*\d[\w.-]*\b)"
    )

    def complete(self, system: str, user: str) -> LLMResponse:
        category = user.split("Task: ", 1)[1].split("\n", 1)[0].strip() if "Task: " in user else ""
        heuristic = self.model.model_id == "heuristic"
        answer = self._answer(category, user, heuristic)
        text = json.dumps(answer)
        return LLMResponse(
            text=text,
            latency_s=random.uniform(0.05, 0.15) if heuristic else random.uniform(0.2, 0.5),
            input_tokens=len(user.split()),
            output_tokens=len(text.split()),
        )

    def _extract_lines(self, user: str) -> list[str]:
        match = self._LOGS.search(user)
        if not match:
            return []
        return [line.split(": ", 1)[1] if ": " in line else line for line in match.group(1).splitlines()]

    def _answer(self, category: str, user: str, heuristic: bool) -> dict:
        lines = self._extract_lines(user)
        if category == "log_parsing":
            if not heuristic:
                return {"templates": ["<*>"] * len(lines)}
            return {"templates": [self._VARIABLE.sub("<*>", line) for line in lines]}
        if category == "anomaly_detection":
            if not heuristic:
                return {"anomalous_indices": []}
            return {
                "anomalous_indices": [
                    i for i, line in enumerate(lines)
                    if any(word in line.lower() for word in self._ANOMALY_WORDS)
                ]
            }
        if category == "pattern_correlation":
            if not heuristic:
                return {"patterns": [{"name": "generic", "description": "logs"}], "correlations": []}
            patterns = []
            seen = set()
            for line in lines:
                lowered = line.lower()
                if any(word in lowered for word in self._ANOMALY_WORDS):
                    name = "_".join(re.findall(r"[a-z]{3,}", lowered)[:4])
                    if name and name not in seen:
                        seen.add(name)
                        patterns.append({"name": name, "description": line})
            correlations = []
            if len(patterns) >= 2:
                correlations = [{"cause": patterns[0]["name"], "effect": p["name"]} for p in patterns[1:]]
            return {"patterns": patterns or [{"name": "none", "description": ""}], "correlations": correlations}
        if category == "metrics_timeseries":
            match = self._SERIES.search(user)
            values = [float(v) for v in match.group(1).split(",")] if match else []
            if not heuristic or len(values) < 3:
                return {"anomalous_indices": []}
            mean = statistics.fmean(values)
            stdev = statistics.pstdev(values) or 1.0
            return {"anomalous_indices": [i for i, v in enumerate(values) if abs(v - mean) > 2.5 * stdev]}
        if category == "root_cause":
            if not heuristic:
                return {"root_cause": "Unknown issue.", "summary": "An incident occurred."}
            error_lines = [l for l in lines if any(w in l.lower() for w in self._ANOMALY_WORDS)]
            focus = error_lines[0] if error_lines else (lines[0] if lines else "unknown")
            return {
                "root_cause": f"Failure indicated by: {focus}",
                "summary": (
                    f"The service degraded during the incident window. Key error observed: {focus}. "
                    f"{len(error_lines)} error events were recorded before recovery."
                ),
            }
        # Judge prompts (no Task: tag) — return a neutral grade.
        return {"score": 5, "reasoning": "mock judge"}


def build_client(model: ModelConfig, config: BenchmarkConfig) -> BaseClient:
    if model.provider in ("openai", "xai"):
        return OpenAICompatibleClient(model, config)
    if model.provider == "anthropic":
        return AnthropicClient(model, config)
    if model.provider == "ollama":
        return OllamaClient(model, config)
    if model.provider == "mock":
        return MockClient(model, config)
    raise ClientError(f"unsupported provider '{model.provider}'")
