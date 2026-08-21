"""LLM provider clients.

- OpenAI-compatible endpoints (OpenAI, xAI, Gemini, and anything speaking
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
        # Effective settings: per-model override falls back to the global value.
        self.timeout = model.request_timeout or config.request_timeout
        self.max_tokens = model.max_tokens or config.max_tokens

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


def _openai_reasoning_model(model_id: str) -> bool:
    """OpenAI o-series and GPT-5+ models reject max_tokens and often temperature."""
    mid = model_id.lower()
    if mid.startswith("o") and len(mid) > 1 and mid[1].isdigit():
        return True
    return mid.startswith("gpt-5")


class OpenAICompatibleClient(BaseClient):
    """OpenAI, xAI Grok, and any other /chat/completions-compatible endpoint."""

    _DEFAULT_BASE_URLS = {
        "openai": "https://api.openai.com/v1",
        "xai": "https://api.x.ai/v1",
        "google": "https://generativelanguage.googleapis.com/v1beta/openai/",
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
            timeout=self.timeout,
        )

    def _chat_payload(self, system: str, user: str) -> dict:
        payload: dict = {
            "model": self.model.model_id,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        reasoning = self.model.provider == "openai" and _openai_reasoning_model(
            self.model.model_id
        )
        if not reasoning:
            payload["temperature"] = self.config.temperature
            payload["max_tokens"] = self.max_tokens
        else:
            payload["max_completion_tokens"] = self.max_tokens
        if self.model.json_mode:
            # The system prompt already instructs "single valid JSON object",
            # which satisfies servers that require the word "json" for this mode.
            payload["response_format"] = {"type": "json_object"}
        if self.model.reasoning_effort:
            # OpenAI GPT-5/o-series and xAI Grok expose this knob; endpoints that
            # don't understand it will 400, which surfaces as a failed run for
            # this model only (others are unaffected).
            payload["reasoning_effort"] = self.model.reasoning_effort
        return payload

    def complete(self, system: str, user: str) -> LLMResponse:
        payload = self._chat_payload(system, user)
        start = time.perf_counter()
        response = _retrying_post(self._http, "/chat/completions", json=payload)
        latency = time.perf_counter() - start
        data = response.json()
        try:
            choice = data["choices"][0]
            text = choice["message"]["content"] or ""
        except (KeyError, IndexError) as exc:
            raise ClientError(f"malformed completion response: {data}") from exc
        if not text.strip():
            # Reasoning models (o-series, GPT-5+) can spend the whole token
            # budget on hidden reasoning and return empty content. Surface a
            # clear, retryable error instead of a downstream "no JSON" failure.
            finish = choice.get("finish_reason")
            hint = (
                " — raise this model's max_tokens (reasoning consumed the budget)"
                if finish == "length"
                else ""
            )
            raise ClientError(f"empty response (finish_reason={finish}){hint}")
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
            timeout=self.timeout,
            max_retries=_MAX_RETRIES,
        )

    def complete(self, system: str, user: str) -> LLMResponse:
        # Sampling params are deliberately omitted: Opus 4.7+ models reject
        # temperature/top_p/top_k with a 400.
        create_kwargs: dict = {
            "model": self.model.model_id,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        if self.model.reasoning_effort:
            # `output_config.effort` controls reasoning depth on current Claude
            # models (thinking is always on; effort is the knob). Passed via
            # extra_body so it works regardless of the installed SDK's typings.
            create_kwargs["extra_body"] = {
                "output_config": {"effort": self.model.reasoning_effort}
            }
        start = time.perf_counter()
        try:
            response = self._client.messages.create(**create_kwargs)
        except self._anthropic.APIError as exc:
            raise ClientError(f"Anthropic API error: {exc}") from exc
        latency = time.perf_counter() - start
        if response.stop_reason == "refusal":
            raise ClientError("Anthropic model refused the request")
        text = "".join(b.text for b in response.content if b.type == "text")
        if not text.strip():
            # Current Claude models (Sonnet 5, Opus 5, Fable 5) run thinking by
            # default, and max_tokens caps thinking + answer together. Long
            # deliberation can hit the cap before any answer text is emitted,
            # leaving an empty response. Surface a clear, retryable error instead
            # of a downstream "no JSON" failure.
            hint = (
                " — raise this model's max_tokens (thinking consumed the budget)"
                if response.stop_reason == "max_tokens"
                else ""
            )
            raise ClientError(f"empty response (stop_reason={response.stop_reason}){hint}")
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
        self._http = httpx.Client(base_url=base_url, timeout=self.timeout)

    def complete(self, system: str, user: str) -> LLMResponse:
        payload = {
            "model": self.model.model_id,
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.max_tokens,
            },
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if self.model.json_mode:
            payload["format"] = "json"  # Ollama's JSON-constraining flag
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
        if category == "multimodal_rca":
            return self._multimodal_rca(user, heuristic)
        if category == "code_generation":
            return self._code_generation(user, heuristic)
        # Judge prompts (no Task: tag) — return a neutral grade.
        return {"score": 5, "reasoning": "mock judge"}

    _METRICS = re.compile(r"<metrics>\n(.*?)\n</metrics>", re.DOTALL)
    _CANDIDATES = re.compile(r"Candidate services \(the culprit is one of these.*?\):\n(.*?)\n", re.DOTALL)

    def _code_generation(self, user: str, heuristic: bool) -> dict:
        """Generate mock code based on the language and task family.

        The heuristic version generates working code for simple cases.
        The naive version generates syntactically valid but non-functional code.
        """
        # Extract language from prompt
        language = "python"  # default
        if "Language: typescript" in user:
            language = "typescript"
        elif "Language: go" in user:
            language = "go"
        elif "Language: rust" in user:
            language = "rust"

        # Extract task family from case ID or spec
        if "slugify" in user.lower():
            if not heuristic:
                return self._naive_code(language)
            return {"code": self._mock_slugify(language)}
        elif "interval" in user.lower() and "merge" in user.lower():
            if not heuristic:
                return self._naive_code(language)
            return {"code": self._mock_interval_merge(language)}
        elif "rate" in user.lower() and "limit" in user.lower():
            if not heuristic:
                return self._naive_code(language)
            return {"code": self._mock_rate_limiter(language)}
        elif "config" in user.lower() and ("merge" in user.lower() or "overlay" in user.lower()):
            if not heuristic:
                return self._naive_code(language)
            return {"code": self._mock_config_merge(language)}
        elif "lru" in user.lower() or "cache" in user.lower():
            if not heuristic:
                return self._naive_code(language)
            return {"code": self._mock_lru_cache(language)}
        elif "log" in user.lower() and "parse" in user.lower():
            if not heuristic:
                return self._naive_code(language)
            return {"code": self._mock_log_parser(language)}

        return self._naive_code(language)

    def _naive_code(self, language: str) -> dict:
        """Return minimal syntactically valid code that does nothing useful."""
        naive_impls = {
            "python": "def placeholder(x):\n    return x",
            "typescript": "function placeholder(x: any): any { return x; }",
            "go": "func Placeholder(x interface{}) interface{} { return x }",
            "rust": "fn placeholder(x: i32) -> i32 { x }",
        }
        return {"code": naive_impls.get(language, naive_impls["python"])}

    def _mock_slugify(self, language: str) -> str:
        """Generate working slugify implementation."""
        impls = {
            "python": '''def slugify(text: str) -> str:
    import re
    text = text.lower()
    text = re.sub(r'[_\\s]+', '-', text)
    text = re.sub(r'[^a-z0-9-]', '', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-')''',
            "typescript": '''function slugify(text: string): string {
    return text.toLowerCase()
        .replace(/[_\\s]+/g, '-')
        .replace(/[^a-z0-9-]/g, '')
        .replace(/-+/g, '-')
        .replace(/^-+|-+$/g, '');
}''',
            "go": '''func Slugify(text string) string {
    text = strings.ToLower(text)
    text = regexp.MustCompile("[_\\s]+").ReplaceAllString(text, "-")
    text = regexp.MustCompile("[^a-z0-9-]").ReplaceAllString(text, "")
    text = regexp.MustCompile("-+").ReplaceAllString(text, "-")
    return strings.Trim(text, "-")
}''',
            "rust": '''fn slugify(text: &str) -> String {
    text.to_lowercase()
        .chars()
        .map(|c| match c {
            '_' | ' ' => '-',
            c if c.is_alphanumeric() || c == '-' => c,
            _ => ' '
        })
        .collect::<String>()
        .split_whitespace()
        .collect::<Vec<_>>()
        .join("")
        .split('-')
        .filter(|s| !s.is_empty())
        .collect::<Vec<_>>()
        .join("-")
}''',
        }
        return impls.get(language, impls["python"])

    def _mock_interval_merge(self, language: str) -> str:
        """Generate working interval merge implementation."""
        impls = {
            "python": '''def merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not intervals:
        return []
    intervals = sorted(intervals)
    merged = [intervals[0]]
    for current in intervals[1:]:
        last = merged[-1]
        if current[0] <= last[1]:
            merged[-1] = (last[0], max(last[1], current[1]))
        else:
            merged.append(current)
    return merged''',
            "typescript": '''function mergeIntervals(intervals: [number, number][]): [number, number][] {
    if (intervals.length === 0) return [];
    intervals.sort((a, b) => a[0] - b[0]);
    const merged: [number, number][] = [intervals[0]];
    for (let i = 1; i < intervals.length; i++) {
        const last = merged[merged.length - 1];
        const current = intervals[i];
        if (current[0] <= last[1]) {
            last[1] = Math.max(last[1], current[1]);
        } else {
            merged.push(current);
        }
    }
    return merged;
}''',
            "go": '''func MergeIntervals(intervals [][2]int) [][2]int {
    if len(intervals) == 0 {
        return [][2]int{}
    }
    sort.Slice(intervals, func(i, j int) bool {
        return intervals[i][0] < intervals[j][0]
    })
    merged := [][2]int{intervals[0]}
    for i := 1; i < len(intervals); i++ {
        last := &merged[len(merged)-1]
        current := intervals[i]
        if current[0] <= last[1] {
            if current[1] > last[1] {
                last[1] = current[1]
            }
        } else {
            merged = append(merged, current)
        }
    }
    return merged
}''',
            "rust": '''fn merge_intervals(mut intervals: Vec<(i32, i32)>) -> Vec<(i32, i32)> {
    if intervals.is_empty() {
        return vec![];
    }
    intervals.sort_by_key(|&(start, _)| start);
    let mut merged = vec![intervals[0]];
    for &current in intervals.iter().skip(1) {
        let last = merged.last_mut().unwrap();
        if current.0 <= last.1 {
            last.1 = last.1.max(current.1);
        } else {
            merged.push(current);
        }
    }
    merged
}''',
        }
        return impls.get(language, impls["python"])

    def _mock_rate_limiter(self, language: str) -> str:
        """Generate basic rate limiter (may not pass all tests but syntactically correct)."""
        impls = {
            "python": '''class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = []
    def allow(self, timestamp: float) -> bool:
        self.requests = [t for t in self.requests if timestamp - t < self.window_seconds]
        if len(self.requests) < self.max_requests:
            self.requests.append(timestamp)
            return True
        return False''',
            "typescript": '''class RateLimiter {
    private maxRequests: number;
    private windowSeconds: number;
    private requests: number[] = [];
    constructor(maxRequests: number, windowSeconds: number) {
        this.maxRequests = maxRequests;
        this.windowSeconds = windowSeconds;
    }
    allow(timestamp: number): boolean {
        this.requests = this.requests.filter(t => timestamp - t < this.windowSeconds);
        if (this.requests.length < this.maxRequests) {
            this.requests.push(timestamp);
            return true;
        }
        return false;
    }
}''',
            "go": '''type RateLimiter struct {
    maxRequests   int
    windowSeconds float64
    requests      []float64
}
func NewRateLimiter(maxRequests int, windowSeconds float64) *RateLimiter {
    return &RateLimiter{maxRequests: maxRequests, windowSeconds: windowSeconds, requests: []float64{}}
}
func (rl *RateLimiter) Allow(timestamp float64) bool {
    newRequests := []float64{}
    for _, t := range rl.requests {
        if timestamp-t < rl.windowSeconds {
            newRequests = append(newRequests, t)
        }
    }
    rl.requests = newRequests
    if len(rl.requests) < rl.maxRequests {
        rl.requests = append(rl.requests, timestamp)
        return true
    }
    return false
}''',
            "rust": '''struct RateLimiter {
    max_requests: usize,
    window_seconds: f64,
    requests: Vec<f64>,
}
impl RateLimiter {
    fn new(max_requests: usize, window_seconds: f64) -> Self {
        RateLimiter { max_requests, window_seconds, requests: Vec::new() }
    }
    fn allow(&mut self, timestamp: f64) -> bool {
        self.requests.retain(|&t| timestamp - t < self.window_seconds);
        if self.requests.len() < self.max_requests {
            self.requests.push(timestamp);
            true
        } else {
            false
        }
    }
}''',
        }
        return impls.get(language, impls["python"])

    def _mock_config_merge(self, language: str) -> str:
        """Generate basic config merge (simplified)."""
        impls = {
            "python": '''def merge_config(base: dict, overlay: dict) -> dict:
    result = base.copy()
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_config(result[key], value)
        else:
            result[key] = value
    return result''',
            "typescript": '''function mergeConfig(base: any, overlay: any): any {
    const result = {...base};
    for (const key in overlay) {
        if (typeof result[key] === 'object' && !Array.isArray(result[key]) && 
            typeof overlay[key] === 'object' && !Array.isArray(overlay[key])) {
            result[key] = mergeConfig(result[key], overlay[key]);
        } else {
            result[key] = overlay[key];
        }
    }
    return result;
}''',
            "go": '''func MergeConfig(base, overlay map[string]interface{}) map[string]interface{} {
    result := make(map[string]interface{})
    for k, v := range base {
        result[k] = v
    }
    for k, v := range overlay {
        if baseMap, ok := result[k].(map[string]interface{}); ok {
            if overlayMap, ok := v.(map[string]interface{}); ok {
                result[k] = MergeConfig(baseMap, overlayMap)
                continue
            }
        }
        result[k] = v
    }
    return result
}''',
            "rust": '''fn merge_config(base: serde_json::Value, overlay: serde_json::Value) -> serde_json::Value {
    use serde_json::{Value, Map};
    match (base, overlay) {
        (Value::Object(mut base_map), Value::Object(overlay_map)) => {
            for (key, value) in overlay_map {
                base_map.insert(key, value);
            }
            Value::Object(base_map)
        },
        (_, overlay) => overlay,
    }
}''',
        }
        return impls.get(language, impls["python"])

    def _mock_lru_cache(self, language: str) -> str:
        """Generate minimal LRU cache (won't pass all tests)."""
        impls = {
            "python": '''class LRUCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache = {}
    def get(self, key: str) -> int | None:
        return self.cache.get(key)
    def put(self, key: str, value: int) -> None:
        if len(self.cache) >= self.capacity and key not in self.cache:
            self.cache.pop(next(iter(self.cache)))
        self.cache[key] = value''',
            "typescript": '''class LRUCache {
    private capacity: number;
    private cache: Map<string, number> = new Map();
    constructor(capacity: number) {
        this.capacity = capacity;
    }
    get(key: string): number | null {
        return this.cache.get(key) ?? null;
    }
    put(key: string, value: number): void {
        if (this.cache.size >= this.capacity && !this.cache.has(key)) {
            const firstKey = this.cache.keys().next().value;
            this.cache.delete(firstKey);
        }
        this.cache.set(key, value);
    }
}''',
            "go": '''type LRUCache struct {
    capacity int
    cache    map[string]int
}
func NewLRUCache(capacity int) *LRUCache {
    return &LRUCache{capacity: capacity, cache: make(map[string]int)}
}
func (c *LRUCache) Get(key string) (int, bool) {
    val, ok := c.cache[key]
    return val, ok
}
func (c *LRUCache) Put(key string, value int) {
    c.cache[key] = value
}''',
            "rust": '''struct LRUCache {
    capacity: usize,
    cache: std::collections::HashMap<String, i32>,
}
impl LRUCache {
    fn new(capacity: usize) -> Self {
        LRUCache { capacity, cache: std::collections::HashMap::new() }
    }
    fn get(&mut self, key: &str) -> Option<i32> {
        self.cache.get(key).copied()
    }
    fn put(&mut self, key: String, value: i32) {
        self.cache.insert(key, value);
    }
}''',
        }
        return impls.get(language, impls["python"])

    def _mock_log_parser(self, language: str) -> str:
        """Generate basic log parser."""
        impls = {
            "python": '''def parse_log_line(line: str) -> dict:
    import re
    pattern = r'\\[(\\w+)\\]\\s+([\\d\\-T:]+)\\s+\\|\\s+([^|]+)\\s+\\|\\s+(.+)'
    match = re.match(pattern, line)
    if match and match.group(1) in ['ERROR', 'WARN', 'INFO', 'DEBUG']:
        return {
            "level": match.group(1),
            "timestamp": match.group(2).strip(),
            "service": match.group(3).strip(),
            "message": match.group(4).strip()
        }
    return {"level": "UNKNOWN", "timestamp": "", "service": "", "message": line}''',
            "typescript": '''function parseLogLine(line: string): {level: string, timestamp: string, service: string, message: string} {
    const pattern = /\\[(\\w+)\\]\\s+([\\d\\-T:]+)\\s+\\|\\s+([^|]+)\\s+\\|\\s+(.+)/;
    const match = line.match(pattern);
    if (match && ['ERROR', 'WARN', 'INFO', 'DEBUG'].includes(match[1])) {
        return {
            level: match[1],
            timestamp: match[2].trim(),
            service: match[3].trim(),
            message: match[4].trim()
        };
    }
    return {level: "UNKNOWN", timestamp: "", service: "", message: line};
}''',
            "go": '''func ParseLogLine(line string) map[string]string {
    pattern := regexp.MustCompile("\\[(\\w+)\\]\\s+([\\d\\-T:]+)\\s+\\|\\s+([^|]+)\\s+\\|\\s+(.+)")
    match := pattern.FindStringSubmatch(line)
    if len(match) > 0 {
        level := match[1]
        validLevels := map[string]bool{"ERROR": true, "WARN": true, "INFO": true, "DEBUG": true}
        if validLevels[level] {
            return map[string]string{
                "level": level,
                "timestamp": strings.TrimSpace(match[2]),
                "service": strings.TrimSpace(match[3]),
                "message": strings.TrimSpace(match[4]),
            }
        }
    }
    return map[string]string{"level": "UNKNOWN", "timestamp": "", "service": "", "message": line}
}''',
            "rust": '''fn parse_log_line(line: &str) -> std::collections::HashMap<String, String> {
    use std::collections::HashMap;
    let valid_levels = ["ERROR", "WARN", "INFO", "DEBUG"];
    let parts: Vec<&str> = line.split('|').collect();
    if parts.len() == 3 {
        let level_part = parts[0].trim();
        if let Some(level) = level_part.strip_prefix('[').and_then(|s| s.strip_suffix(']')) {
            if valid_levels.contains(&level) {
                let mut result = HashMap::new();
                result.insert("level".to_string(), level.to_string());
                result.insert("timestamp".to_string(), "".to_string());
                result.insert("service".to_string(), parts[1].trim().to_string());
                result.insert("message".to_string(), parts[2].trim().to_string());
                return result;
            }
        }
    }
    let mut result = HashMap::new();
    result.insert("level".to_string(), "UNKNOWN".to_string());
    result.insert("timestamp".to_string(), "".to_string());
    result.insert("service".to_string(), "".to_string());
    result.insert("message".to_string(), line.to_string());
    result
}''',
        }
        return impls.get(language, impls["python"])

    _METRICS = re.compile(r"<metrics>\n(.*?)\n</metrics>", re.DOTALL)
    _CANDIDATES = re.compile(r"Candidate services \(the culprit is one of these.*?\):\n(.*?)\n", re.DOTALL)

    def _multimodal_rca(self, user: str, heuristic: bool) -> dict:
        """Rule-based baseline: pick the service with the highest peak CPU.

        A deliberately shallow strategy — it reads one modality and always cites
        it — so it lands the CPU cases, misses the log-only ones, and takes a
        grounding penalty whenever metrics aren't what carried the signal.
        """
        services = []
        match = self._CANDIDATES.search(user)
        if match:
            services = [s.strip() for s in match.group(1).split(",") if s.strip()]
        if not heuristic:
            return {
                "culprit_service": services[0] if services else "none",
                "fault_type": "cpu_saturation",
                "evidence": [],
                "summary": "A service degraded during the window.",
            }

        best_service, best_cpu = "none", 0.0
        block = self._METRICS.search(user)
        if block:
            current = ""
            for line in block.group(1).splitlines():
                if not line.startswith("  "):
                    current = line.strip()
                elif line.strip().startswith("cpu%:"):
                    values = []
                    for token in line.split(":", 1)[1].split():
                        try:
                            values.append(float(token))
                        except ValueError:
                            continue
                    peak = max(values, default=0.0)
                    if peak > best_cpu:
                        best_service, best_cpu = current, peak

        return {
            "culprit_service": best_service,
            "fault_type": "cpu_saturation",
            "evidence": [
                {"modality": "metrics", "observation": f"{best_service} peaked at {best_cpu:.1f}% CPU"}
            ],
            "summary": (
                f"{best_service} showed the highest CPU utilization during the window, "
                f"peaking at {best_cpu:.1f}%."
            ),
        }


def build_client(model: ModelConfig, config: BenchmarkConfig) -> BaseClient:
    if model.provider in ("openai", "xai", "google"):
        return OpenAICompatibleClient(model, config)
    if model.provider == "anthropic":
        return AnthropicClient(model, config)
    if model.provider == "ollama":
        return OllamaClient(model, config)
    if model.provider == "mock":
        return MockClient(model, config)
    raise ClientError(f"unsupported provider '{model.provider}'")
