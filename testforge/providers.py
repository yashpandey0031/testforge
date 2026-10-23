"""LLM providers behind one tiny interface: provider.complete(prompt) -> str.
Responses are cached on disk by hash, so re-runs are free, fast and reproducible."""
import hashlib
import os
from pathlib import Path

import httpx


class Provider:
    name = "base"

    def __init__(self, cache_dir=".testforge_cache"):
        self.cache = Path(cache_dir)

    def _call(self, prompt: str) -> str:
        raise NotImplementedError

    def complete(self, prompt: str) -> str:
        key = hashlib.sha256(f"{self.name}|{prompt}".encode()).hexdigest()[:24]
        f = self.cache / f"{key}.txt"
        if f.exists():
            return f.read_text(encoding="utf-8")
        text = self._call(prompt)
        self.cache.mkdir(exist_ok=True)
        f.write_text(text, encoding="utf-8")
        return text


class GroqProvider(Provider):
    """Free tier friendly. Needs GROQ_API_KEY."""
    def __init__(self, model=None, **kw):
        super().__init__(**kw)
        self.model = model or os.environ.get("TESTFORGE_GROQ_MODEL", "llama-3.3-70b-versatile")
        self.name = f"groq:{self.model}"

    def _call(self, prompt):
        r = httpx.post("https://api.groq.com/openai/v1/chat/completions", timeout=120,
                       headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
                       json={"model": self.model, "temperature": 0,
                             "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


class AnthropicProvider(Provider):
    """Needs ANTHROPIC_API_KEY."""
    def __init__(self, model=None, **kw):
        super().__init__(**kw)
        self.model = model or os.environ.get("TESTFORGE_ANTHROPIC_MODEL", "claude-sonnet-5-5")
        self.name = f"anthropic:{self.model}"

    def _call(self, prompt):
        r = httpx.post("https://api.anthropic.com/v1/messages", timeout=180,
                       headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"},
                       json={"model": self.model, "max_tokens": 8000, "temperature": 0,
                             "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        return r.json()["content"][0]["text"]


def get_provider(name: str) -> Provider:
    if name == "groq":
        return GroqProvider()
    if name == "anthropic":
        return AnthropicProvider()
    raise ValueError(f"unknown provider {name!r} (use groq or anthropic)")
