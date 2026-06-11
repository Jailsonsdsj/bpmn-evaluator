"""Provider-agnostic chat-model factory.

Every agent builds its chat model through ``get_chat_model()`` so no agent hard-codes
a provider. Selection is driven by environment variables:

- ``LLM_PROVIDER`` — which provider to use (e.g. ``anthropic``, ``google_genai``,
  ``openai``, ``groq``, ``mistralai``, ``ollama``).
- ``MODEL_NAME``  — the model id for that provider (e.g. ``claude-sonnet-4-6``).
- ``LLM_BASE_URL`` — optional. Point the provider at a custom/self-hosted endpoint.
  This is how local models are wired up: an OpenAI-compatible server (LM Studio,
  llama.cpp, vLLM, text-generation-webui) uses ``LLM_PROVIDER=openai`` plus this URL;
  Ollama on a non-default host (e.g. inside Docker) sets it too. Local Ollama on the
  default ``http://localhost:11434`` needs nothing extra.

Any provider supported by LangChain's ``init_chat_model`` works as long as its
integration package is installed; the table below only adds friendlier errors and
API-key handling for the common ones. To add a provider: install its package
(``pip install langchain-<provider>``) and set ``LLM_PROVIDER`` + ``MODEL_NAME``.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

load_dotenv()

# provider -> (pip package, env var holding the API key). env_key None => no key (local).
_PROVIDERS: dict[str, dict[str, str | None]] = {
    "anthropic":    {"package": "langchain-anthropic",    "env_key": "ANTHROPIC_API_KEY"},
    "google_genai": {"package": "langchain-google-genai", "env_key": "GEMINI_API_KEY"},
    "openai":       {"package": "langchain-openai",        "env_key": "OPENAI_API_KEY"},
    "groq":         {"package": "langchain-groq",          "env_key": "GROQ_API_KEY"},
    "mistralai":    {"package": "langchain-mistralai",     "env_key": "MISTRAL_API_KEY"},
    "ollama":       {"package": "langchain-ollama",        "env_key": None},
}

SUPPORTED_PROVIDERS = tuple(_PROVIDERS)


def resolve_provider() -> str:
    """Return the configured provider name (lower-cased).

    Uses ``LLM_PROVIDER`` when set. When it is empty, falls back to inferring the
    provider from whichever API key is present — preserving the old key-based
    selection so existing ``.env`` files keep working.
    """
    provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    if provider:
        return provider
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        return "google_genai"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    raise ValueError(
        "No LLM provider configured. Set LLM_PROVIDER (one of: "
        f"{', '.join(SUPPORTED_PROVIDERS)}) and MODEL_NAME in your .env."
    )


def _prepare_credentials(provider: str) -> None:
    """Ensure the provider's SDK can find its API key.

    langchain-google-genai reads ``GOOGLE_API_KEY``, but the project documents the
    Gemini key as ``GEMINI_API_KEY`` — bridge it here. Every other provider reads
    its own standard env var, which ``init_chat_model`` picks up automatically.
    """
    if provider == "google_genai":
        gemini = os.getenv("GEMINI_API_KEY")
        if gemini and not os.getenv("GOOGLE_API_KEY"):
            os.environ["GOOGLE_API_KEY"] = gemini


def get_chat_model(
    *,
    temperature: 0,
    max_tokens: int | None = None,
    **overrides: object,
) -> BaseChatModel:
    """Build the chat model selected by ``LLM_PROVIDER`` + ``MODEL_NAME``.

    ``temperature`` / ``max_tokens`` are forwarded only when provided; extra keyword
    arguments override anything passed to the underlying integration. Raises
    ``ValueError`` with an actionable message when the provider/model is missing or
    its integration package is not installed.
    """
    provider = resolve_provider()
    model = os.getenv("MODEL_NAME", "").strip()
    if not model:
        raise ValueError("MODEL_NAME is not set. Configure it in your .env.")

    _prepare_credentials(provider)

    kwargs: dict[str, object] = {}
    base_url = os.getenv("LLM_BASE_URL", "").strip()
    if base_url:
        # Forwarded to the integration (ChatOpenAI / ChatOllama accept base_url),
        # so a local OpenAI-compatible server or a remote Ollama host can be used.
        kwargs["base_url"] = base_url
    if temperature is not None:
        kwargs["temperature"] = temperature
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    kwargs.update(overrides)

    try:
        return init_chat_model(model, model_provider=provider, **kwargs)
    except ImportError as exc:
        package = (_PROVIDERS.get(provider) or {}).get("package")
        hint = f" Install it with `pip install {package}`." if package else ""
        raise ValueError(
            f"LLM provider '{provider}' is selected but its integration package is "
            f"not installed.{hint}"
        ) from exc
    except ValueError as exc:
        raise ValueError(
            f"Could not initialize provider '{provider}' with model '{model}'. "
            f"Supported out of the box: {', '.join(SUPPORTED_PROVIDERS)} (any provider "
            f"supported by langchain.init_chat_model also works if its package is "
            f"installed). Original error: {exc}"
        ) from exc


def supports_cache_control(llm: BaseChatModel) -> bool:
    """True for Anthropic models, which accept ``cache_control`` on invoke.

    Lets callers special-case Anthropic prompt caching without importing
    ``ChatAnthropic`` (keeping them provider-agnostic).
    """
    return llm.__class__.__name__ == "ChatAnthropic"
