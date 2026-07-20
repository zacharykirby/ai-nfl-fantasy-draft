#!/usr/bin/env python3
"""Shared OpenRouter client utilities."""

import json
import os
import re
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv


DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_OPENROUTER_MODEL = "openai/gpt-4o-mini"

load_dotenv()


class OpenRouterClient:
    """Minimal OpenRouter chat-completions client."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        app_title: Optional[str] = None,
        http_referer: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.model = model or os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL)
        self.base_url = (base_url or os.getenv("OPENROUTER_BASE_URL", DEFAULT_OPENROUTER_BASE_URL)).rstrip("/")
        self.app_title = app_title or os.getenv("OPENROUTER_APP_TITLE", "NFL Fantasy Draft Assistant")
        self.http_referer = http_referer or os.getenv("OPENROUTER_HTTP_REFERER")

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict[str, Any]] = None,
        timeout: int = 90,
    ) -> str:
        """Send a non-streaming chat completion request and return message text."""
        if not self.api_key:
            return "Error: OPENROUTER_API_KEY is not set"

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if response_format is not None:
            payload["response_format"] = response_format

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Title": self.app_title,
        }
        if self.http_referer:
            headers["HTTP-Referer"] = self.http_referer

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=timeout,
            )
            if response.status_code != 200:
                return f"Error: OpenRouter returned status {response.status_code}: {response.text[:500]}"

            result = response.json()
            choices = result.get("choices", [])
            if not choices:
                return "Error: OpenRouter returned no choices"

            content = choices[0].get("message", {}).get("content", "")
            return strip_reasoning_blocks(content).strip()
        except requests.exceptions.RequestException as exc:
            return f"Error: Could not connect to OpenRouter: {exc}"
        except Exception as exc:
            return f"Error: {exc}"


def strip_reasoning_blocks(text: str) -> str:
    """Remove common hidden-reasoning tag blocks from model output."""
    for tag in ("think", "thinking", "reasoning"):
        text = re.sub(fr"<{tag}>.*?</{tag}>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(fr"</?{tag}>", "", text, flags=re.IGNORECASE)
    return re.sub(r"\n\s*\n\s*\n", "\n\n", text).strip()


def parse_json_object(text: str) -> Dict[str, Any]:
    """Parse a model response that should contain a JSON object."""
    cleaned = strip_reasoning_blocks(text).strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json", 1)[1]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if "```" in cleaned:
        cleaned = cleaned.split("```", 1)[0]
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise
