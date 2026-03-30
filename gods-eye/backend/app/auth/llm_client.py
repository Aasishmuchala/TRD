"""OpenAI-compatible LLM client with device auth token management.

Replaces direct Anthropic client usage. Works with any OpenAI-compatible API
(OpenAI, Nous Research, local vLLM, etc.) using tokens from device_auth.py.

Also supports direct API key mode for backward compatibility.
"""

import json
import logging
from typing import Optional, Dict, Any

import httpx

from app.config import config
from app.auth.device_auth import get_auth_manager, PROVIDERS

logger = logging.getLogger(__name__)


class LLMClient:
    """Async OpenAI-compatible chat completion client.

    Supports two auth modes:
      1. Device auth (OAuth tokens from Codex login)
      2. Direct API key (LLM_API_KEY env var)

    Usage:
        client = LLMClient()
        response = await client.chat_completion(
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0.3,
            max_tokens=500,
        )
        print(response)  # The assistant's text response
    """

    def __init__(self):
        self._http = httpx.AsyncClient(timeout=120.0)

    async def chat_completion(
        self,
        messages: list,
        model: str = None,
        temperature: float = None,
        max_tokens: int = 500,
        response_format: Optional[Dict] = None,
    ) -> str:
        """Send a chat completion request to the configured LLM provider.

        Args:
            messages: List of {"role": "...", "content": "..."} dicts
            model: Model override (defaults to config.MODEL)
            temperature: Sampling temperature (defaults to config.TEMPERATURE)
            max_tokens: Max response tokens
            response_format: Optional response format spec

        Returns:
            The assistant's text response

        Raises:
            RuntimeError: If not authenticated or API call fails
        """
        model = model or config.MODEL
        temperature = temperature if temperature is not None else config.TEMPERATURE

        # Get auth token and base URL
        base_url, headers = await self._get_auth_headers()

        # Build request payload
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        # Make the API call
        url = f"{base_url}/chat/completions"

        try:
            response = await self._http.post(url, json=payload, headers=headers)

            if response.status_code == 401:
                # Token might be expired, try refresh
                logger.info("Got 401, attempting token refresh...")
                auth_mgr = get_auth_manager()
                token = await auth_mgr.get_valid_token()
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                    response = await self._http.post(url, json=payload, headers=headers)
                else:
                    raise RuntimeError(
                        "Authentication expired. Please re-login via /api/auth/login"
                    )

            response.raise_for_status()
            data = response.json()

            # Extract text from OpenAI-compatible response
            choices = data.get("choices", [])
            if not choices:
                raise RuntimeError(f"Empty response from LLM: {data}")

            return choices[0]["message"]["content"]

        except httpx.HTTPStatusError as e:
            error_body = e.response.text
            logger.error(f"LLM API error {e.response.status_code}: {error_body}")
            raise RuntimeError(f"LLM API error: {error_body}")
        except httpx.HTTPError as e:
            logger.error(f"Network error calling LLM: {e}")
            raise RuntimeError(f"Network error: {e}")

    async def _get_auth_headers(self) -> tuple:
        """Get the base URL and auth headers for the current provider.

        Returns (base_url, headers_dict)
        """
        provider_key = config.LLM_PROVIDER
        provider = PROVIDERS.get(provider_key, PROVIDERS.get("openai"))

        # Mode 1: Direct API key (backward compat + simple setup)
        if config.LLM_API_KEY:
            base_url = config.LLM_INFERENCE_URL or provider.get("inference_base", "https://api.openai.com/v1")
            return base_url, {
                "Authorization": f"Bearer {config.LLM_API_KEY}",
                "Content-Type": "application/json",
            }

        # Mode 2: Device auth tokens
        auth_mgr = get_auth_manager(provider_key)
        token = await auth_mgr.get_valid_token()

        if not token:
            raise RuntimeError(
                f"Not authenticated with {provider.get('name', provider_key)}. "
                f"Please login via POST /api/auth/login"
            )

        base_url = config.LLM_INFERENCE_URL or provider.get("inference_base", "https://api.openai.com/v1")
        return base_url, {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def close(self):
        await self._http.aclose()


# ─── Global singleton ─────────────────────────────────────────────────────
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get the global LLM client singleton."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
