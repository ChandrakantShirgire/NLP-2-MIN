"""Thin LLM client. Backends: gemini (default, REST) and mock (offline plumbing tests only)."""
import json
import os
import time
from pathlib import Path

import requests

ROOT = Path(__file__).parent


def _load_env():
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()


class LLM:
    def __init__(self, backend=None, model=None, rpm=10):
        self.backend = backend or os.getenv("LLM_BACKEND", "gemini")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.min_gap = 60.0 / rpm
        self._last = 0.0

    def generate(self, prompt, system=None, temperature=0.2, max_tokens=400):
        if self.backend == "mock":
            return self._mock(prompt)
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY missing. Copy .env.example to .env and paste your key.")
        body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if "2.5" in self.model:                      # no hidden "thinking" tokens: keeps answers short and cheap
            body["generationConfig"]["thinkingConfig"] = {"thinkingBudget": 0}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        for attempt in range(6):
            wait = self.min_gap - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.time()
            r = requests.post(url, headers={"x-goog-api-key": key, "Content-Type": "application/json"}, json=body, timeout=60)
            if r.status_code in (429, 500, 503):
                time.sleep(5 * 2 ** attempt)
                continue
            if r.status_code != 200:
                raise RuntimeError(f"Gemini API {r.status_code}: {r.text[:300]}")
            c = r.json().get("candidates", [{}])[0]
            parts = c.get("content", {}).get("parts", [])
            return "".join(p.get("text", "") for p in parts).strip()
        raise RuntimeError("Gemini API kept returning 429/5xx; lower --rpm or retry later.")

    @staticmethod
    def _mock(prompt):
        p = prompt.lower()
        if "sentiment" in p:
            return "positive"
        if "genre" in p:
            return "drama"
        return "I don't know." if "unknown" in p else "A short mock answer about the film."
