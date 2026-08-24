"""Load models into a (possibly remote) LM Studio server before benchmarking.

LM Studio's OpenAI-compatible endpoint only answers for whatever is currently
in memory, and its JIT loader uses the model's saved default context length —
which is often far smaller than the observability dumps this benchmark feeds
it. Sweeping several local models in one run therefore means loading each in
turn by hand, in the GUI, on whichever machine holds the GPU.

The native LM Studio API is served on the same port as the OpenAI-compatible
one, so the runner can drive loading itself, including against a remote host.
"""

from __future__ import annotations

from typing import Any, Callable, Optional
from urllib.parse import urlparse

from core.config import ModelConfig

# LM Studio unloads an idle model after this many seconds by default. A sweep
# can leave a model idle while a judge call or a slow category runs, and having
# it silently evicted mid-benchmark would restart it on the saved default
# context. Hold it until we choose to swap it out.
_KEEP_LOADED = None

_DEFAULT_PORT = 1234


class LMStudioError(RuntimeError):
    """Could not put the requested model into memory."""


def is_managed(model: ModelConfig) -> bool:
    """True when this model opts into automatic loading."""
    return model.context_length is not None and bool(model.base_url)


def control_endpoint(base_url: str) -> str:
    """Derive the LM Studio "host:port" from an OpenAI-compatible base_url."""
    parsed = urlparse(base_url)
    if not parsed.hostname:
        raise LMStudioError(f"cannot derive an LM Studio host from {base_url!r}")
    return f"{parsed.hostname}:{parsed.port or _DEFAULT_PORT}"


def _load_config(model: ModelConfig) -> dict[str, Any]:
    config: dict[str, Any] = {"contextLength": model.context_length}
    if model.gpu_ratio is not None:
        config["gpu"] = {"ratio": model.gpu_ratio}
    return config


def ensure_loaded(
    model: ModelConfig, log: Optional[Callable[[str], None]] = None
) -> None:
    """Make `model` the loaded model on its LM Studio host, at its context length.

    No-op for models that don't opt in. Raises LMStudioError if the model can't
    be loaded, so the caller can fail the model outright rather than silently
    benchmarking whatever happened to be in memory.
    """
    if not is_managed(model):
        return

    try:
        import lmstudio
    except ImportError as exc:  # pragma: no cover - depends on install
        raise LMStudioError(
            "context_length needs the LM Studio SDK: pip install lmstudio"
        ) from exc

    endpoint = control_endpoint(model.base_url or "")
    note = log or (lambda _message: None)

    try:
        with lmstudio.Client(endpoint) as client:
            for handle in client.llm.list_loaded():
                if (
                    handle.identifier == model.model_id
                    and handle.get_context_length() == model.context_length
                ):
                    note(f"{model.name}: already loaded @ {model.context_length} ctx")
                    return
                # Anything else is evicted first. These models are sized to fill
                # the GPU on their own, so loading a second one on top would
                # spill into system RAM or fail outright.
                note(f"{model.name}: unloading {handle.identifier}")
                handle.unload()

            note(f"{model.name}: loading {model.model_id} @ {model.context_length} ctx")
            client.llm.load_new_instance(
                model.model_id,
                ttl=_KEEP_LOADED,
                config=_load_config(model),
            )
    except LMStudioError:
        raise
    except Exception as exc:
        raise LMStudioError(f"{endpoint}: {exc}") from exc
