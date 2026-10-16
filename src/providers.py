"""Small REST adapters. No provider SDKs, retries, tools, or key-bearing URLs."""

import json
import socket
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from src.config import Settings

MAX_RESPONSE_BYTES = 1_000_000


class ProviderError(RuntimeError):
    """Only fixed, credential-free error categories cross this boundary."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProviderError("redirect refused")


def post_json(url: str, payload: dict, headers: dict, timeout: float) -> dict:
    """Bound response size/time and never surface provider bodies or request headers."""
    body = json.dumps(payload).encode()
    if len(body) > 300_000:
        raise ProviderError("evidence exceeds request limit")
    request = Request(
        url, data=body, headers={"Content-Type": "application/json", **headers}, method="POST"
    )
    try:
        with build_opener(NoRedirect()).open(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ProviderError("response exceeds size limit")
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ProviderError("malformed response")
        return result
    except HTTPError as exc:
        category = (
            "authentication failure"
            if exc.code in {401, 403}
            else "quota or rate limit"
            if exc.code == 429
            else "model or request unavailable"
            if exc.code in {400, 404}
            else "provider unavailable"
        )
        raise ProviderError(category) from None
    except (TimeoutError, socket.timeout):
        raise ProviderError("timeout") from None
    except (URLError, OSError, HTTPException):
        raise ProviderError("network failure") from None
    except (ValueError, UnicodeError, RecursionError):
        raise ProviderError("malformed response") from None


def generate(provider: str, settings: Settings, system: str, prompt: str, schema: dict) -> str:
    """One bounded attempt against exactly the selected provider."""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    try:
        if provider == "gemini":
            if not settings.gemini_api_key:
                raise ProviderError("required key missing")
            data = post_json(
                "https://generativelanguage.googleapis.com/v1beta/models/"
                + quote(settings.gemini_model, safe="")
                + ":generateContent",
                {
                    "systemInstruction": {"parts": [{"text": system}]},
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0,
                        "maxOutputTokens": 8192,
                        "responseMimeType": "application/json",
                        "responseJsonSchema": schema,
                    },
                },
                {"x-goog-api-key": settings.gemini_api_key},
                settings.llm_timeout_seconds,
            )
            return "".join(
                part.get("text", "") for part in data["candidates"][0]["content"]["parts"]
            )
        if provider == "groq":
            if not settings.groq_api_key:
                raise ProviderError("required key missing")
            data = post_json(
                "https://api.groq.com/openai/v1/chat/completions",
                {
                    "model": settings.groq_model,
                    "messages": messages,
                    "temperature": 0,
                    "max_tokens": 8192,
                    "response_format": {"type": "json_object"},
                },
                {"Authorization": "Bearer " + settings.groq_api_key},
                settings.llm_timeout_seconds,
            )
            return data["choices"][0]["message"]["content"]
        if provider == "ollama":
            parsed = urlsplit(settings.ollama_base_url)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
                or (
                    parsed.scheme == "http"
                    and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
                )
            ):
                raise ProviderError("unsafe local provider URL")
            data = post_json(
                settings.ollama_base_url.rstrip("/") + "/api/chat",
                {
                    "model": settings.ollama_model,
                    "messages": messages,
                    "format": schema,
                    "stream": False,
                    "think": False,
                    "options": {"temperature": 0, "num_predict": 8192},
                },
                {},
                settings.llm_timeout_seconds,
            )
            return data["message"]["content"]
        raise ProviderError("unsupported provider")
    except (KeyError, IndexError, TypeError, AttributeError):
        raise ProviderError("malformed response") from None
