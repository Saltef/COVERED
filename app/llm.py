"""Swappable LLM provider (OpenRouter, OpenAI-compatible).

One place to pick the model (cheap by default, any OpenRouter id via OPENROUTER_MODEL). The ops
co-pilot and the explainer both call through here. Degrades gracefully: available() is False
without a key, and callers fall back to deterministic behaviour.
"""
from __future__ import annotations

from app.config import get_settings


def available() -> bool:
    return bool(get_settings().openrouter_api_key)


def model() -> str:
    return get_settings().openrouter_model


def _client():
    from openai import OpenAI
    s = get_settings()
    return OpenAI(
        base_url=s.openrouter_base_url,
        api_key=s.openrouter_api_key,
        default_headers={"HTTP-Referer": "https://covered.app", "X-Title": "Covered"},
    )


def chat(messages: list, tools: list | None = None, max_tokens: int = 1024):
    """Call chat.completions. Returns the raw OpenAI-style response."""
    kwargs: dict = {"model": model(), "messages": messages, "max_tokens": max_tokens}
    if tools:
        kwargs["tools"] = tools
    return _client().chat.completions.create(**kwargs)


def chat_vision(prompt: str, image_data_url: str, max_tokens: int = 500):
    """Send a text prompt + an image (data URL) to a multimodal model (e.g. gpt-4o-mini)."""
    content = [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": image_data_url}},
    ]
    return _client().chat.completions.create(
        model=model(), max_tokens=max_tokens,
        messages=[{"role": "user", "content": content}])
