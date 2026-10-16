"""Environment-backed application configuration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, field_validator

LLMProvider = Literal["gemini", "groq", "ollama", "deterministic"]


class Settings(BaseModel):
    """Validated settings; secret values are excluded from serialization/errors."""

    model_config = ConfigDict(hide_input_in_errors=True)

    falkordb_host: str = Field(default="localhost", min_length=1)
    falkordb_port: int = Field(default=6379, ge=1, le=65535)
    falkordb_graph: str = Field(default="blast_radius", min_length=1)
    llm_provider: LLMProvider = "deterministic"
    gemini_api_key: str | None = Field(default=None, repr=False, exclude=True)
    gemini_model: str = Field(default="gemini-2.5-flash", min_length=1)
    groq_api_key: str | None = Field(default=None, repr=False, exclude=True)
    groq_model: str = Field(default="llama-3.3-70b-versatile", min_length=1)
    ollama_base_url: str = Field(default="http://localhost:11434", min_length=1)
    ollama_model: str = Field(default="qwen3:8b", min_length=1)
    llm_fallback_enabled: bool = False
    llm_timeout_seconds: float = Field(default=20, gt=0, le=120)

    @field_validator(
        "falkordb_host",
        "falkordb_graph",
        "gemini_model",
        "groq_model",
        "ollama_base_url",
        "ollama_model",
    )
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        """Reject values that contain only whitespace."""
        value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        if len(value) > 512 or any(ord(char) < 32 for char in value):
            raise ValueError("must be at most 512 characters without control characters")
        return value

    @field_validator("llm_provider", mode="before")
    @classmethod
    def normalize_provider(cls, value: object) -> object:
        """Allow provider names to be entered without case sensitivity."""
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("gemini_api_key", "groq_api_key", mode="before")
    @classmethod
    def normalize_optional_secret(cls, value: object) -> object:
        """Treat blank API keys as unconfigured."""
        return value.strip() or None if isinstance(value, str) else value

    @property
    def provider_key_configured(self) -> bool | None:
        """Return key presence, or None when the provider needs no API key."""
        if self.llm_provider == "gemini":
            return bool(self.gemini_api_key)
        if self.llm_provider == "groq":
            return bool(self.groq_api_key)
        return None

    @classmethod
    def from_env(cls, env_file: str | Path | None = ".env") -> "Settings":
        """Load known settings from an optional dotenv file and the environment."""
        values: dict[str, str | None] = {}
        if env_file is not None:
            values.update(dotenv_values(env_file, interpolate=False))
        values.update(os.environ)

        fields = {
            name: values[env_name]
            for name in cls.model_fields
            if (env_name := name.upper()) in values
        }
        # Keys are read only from the process environment, never a source file.
        for name in ("gemini_api_key", "groq_api_key"):
            fields[name] = os.environ.get(name.upper())
        return cls.model_validate(fields)
