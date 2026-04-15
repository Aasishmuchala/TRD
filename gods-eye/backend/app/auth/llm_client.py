"""Multi-format LLM client with support for OpenAI and Anthropic APIs.

Supports:
  - OpenAI-compatible APIs (/chat/completions) — OpenAI, Nous, vLLM, etc.
  - Anthropic-compatible APIs (/v1/messages) — Anthropic, OpusCode Pro, etc.

Auth modes:
  1. Direct API key (LLM_API_KEY env var) — recommended for OpusCode Pro
  2. Device auth (OAuth tokens from Codex login) — for OpenAI/Nous
"""

import json
import logging
from typing import Optional, Dict, Any, List

import httpx

from app.config import config
from app.auth.device_auth import get_auth_manager, PROVIDERS

logger = logging.getLogger(__name__)


class LLMClient:
    """Async LLM chat completion client supporting OpenAI and Anthropic formats.

    Usage:
        client = LLMClient()
        response = await client.chat_completion(
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0.3,
            max_tokens=500,
        )
        print(response)  # The assistant's text response
    """

    ANTHROPIC_VERSION = "2023-06-01"

    def __init__(self):
        # Opus + extended thinking routinely takes 60-90s per call.
        # Short connect timeout, long read timeout so we don't cut off mid-generation.
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=150.0, write=30.0, pool=10.0)
        )

    def _get_api_format(self) -> str:
        """Determine API format based on provider config.

        Returns 'anthropic' or 'openai'.
        """
        provider_key = config.LLM_PROVIDER
        provider = PROVIDERS.get(provider_key, PROVIDERS.get("openai"))
        return provider.get("api_format", "openai")

    async def chat_completion(
        self,
        messages: list,
        model: str = None,
        temperature: float = None,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None,
    ) -> str:
        """Send a chat completion request to the configured LLM provider.

        Args:
            messages: List of {"role": "...", "content": "..."} dicts
            model: Model override (defaults to config.MODEL)
            temperature: Sampling temperature (defaults to config.TEMPERATURE)
            max_tokens: Max response tokens
            response_format: Optional response format spec (OpenAI only)

        Returns:
            The assistant's text response

        Raises:
            RuntimeError: If not authenticated or API call fails
        """
        api_format = self._get_api_format()

        if api_format == "anthropic":
            return await self._anthropic_completion(
                messages, model, temperature, max_tokens
            )
        else:
            return await self._openai_completion(
                messages, model, temperature, max_tokens, response_format
            )

    # ─── Anthropic Messages API (/v1/messages) ───────────────────────────

    async def _anthropic_completion(
        self,
        messages: list,
        model: str = None,
        temperature: float = None,
        max_tokens: int = 4096,
    ) -> str:
        """Call Anthropic-compatible API (OpusCode Pro, Anthropic direct)."""
        model = model or config.MODEL
        temperature = temperature if temperature is not None else config.TEMPERATURE

        base_url, headers = await self._get_anthropic_headers()

        # Extract system message(s) from messages list
        # Anthropic API takes system as a top-level param, not in messages
        system_parts = []
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_parts.append(msg["content"])
            else:
                user_messages.append(msg)

        # Ensure messages alternate user/assistant and start with user
        # If first message after system extraction is assistant, prepend empty user
        if user_messages and user_messages[0]["role"] == "assistant":
            user_messages.insert(0, {"role": "user", "content": "Continue."})

        # OpusCode Pro forces extended thinking on all models.
        # Cap the thinking budget so the model spends ≤1024 tokens thinking
        # and has the remaining tokens for the JSON output (~200-400 tokens).
        # Without this cap, thinking consumes ALL of max_tokens and no text is produced.
        THINKING_BUDGET = 1024
        effective_max_tokens = max(max_tokens, THINKING_BUDGET + 500)

        payload = {
            "model": model,
            "messages": user_messages,
            "temperature": temperature,
            "max_tokens": effective_max_tokens,
            "thinking": {"type": "enabled", "budget_tokens": THINKING_BUDGET},
        }

        if system_parts:
            payload["system"] = "\n\n".join(system_parts)

        url = f"{base_url}/v1/messages"

        try:
            logger.info(f"Anthropic API call: model={model}, url={url}, msgs={len(user_messages)}")

            # Retry on transient 5xx errors (502/503/520 from proxy)
            max_retries = 5
            response = None
            for attempt in range(max_retries):
                response = await self._http.post(url, json=payload, headers=headers)
                if response.status_code not in (502, 503, 520, 529):
                    break
                if attempt < max_retries - 1:
                    wait = 2 ** attempt  # 1s, 2s
                    logger.warning(f"Anthropic API returned {response.status_code}, retry {attempt+1}/{max_retries} in {wait}s")
                    import asyncio
                    await asyncio.sleep(wait)

            if response.status_code == 401:
                error_body = response.text
                logger.error(f"Anthropic API auth error 401: {error_body}")
                raise RuntimeError(f"Anthropic API auth error: {error_body}")

            response.raise_for_status()
            data = response.json()

            # Anthropic response format: {"content": [{"type": "text", "text": "..."}]}
            content_blocks = data.get("content", [])
            if not content_blocks:
                raise RuntimeError(f"Empty response from Anthropic API: {data}")

            # Concatenate all text blocks
            text_parts = []
            for block in content_blocks:
                if block.get("type") == "text":
                    text_parts.append(block["text"])

            if not text_parts:
                raise RuntimeError(f"No text content in Anthropic response: {data}")

            result = "\n".join(text_parts)
            logger.info(f"Anthropic API success: {len(result)} chars, model={data.get('model', model)}")
            return result

        except httpx.HTTPStatusError as e:
            error_body = e.response.text
            logger.error(f"Anthropic API error {e.response.status_code}: {error_body}")
            raise RuntimeError(f"Anthropic API error: {error_body}")
        except httpx.HTTPError as e:
            logger.error(f"Network error calling Anthropic API: {e}")
            raise RuntimeError(f"Network error: {e}")

    async def _get_anthropic_headers(self) -> tuple:
        """Get base URL and headers for Anthropic-format API.

        Returns (base_url, headers_dict)
        """
        provider_key = config.LLM_PROVIDER
        provider = PROVIDERS.get(provider_key, PROVIDERS.get("openai"))

        base_url = config.LLM_INFERENCE_URL or provider.get(
            "inference_base", "https://api.anthropic.com"
        )

        api_key = config.LLM_API_KEY
        if not api_key:
            raise RuntimeError(
                "No API key configured for Anthropic provider. "
                "Set LLM_API_KEY in your .env file."
            )

        return base_url, {
            "x-api-key": api_key,
            "anthropic-version": self.ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

    # ─── OpenAI Chat Completions API (/chat/completions) ─────────────────

    async def _openai_completion(
        self,
        messages: list,
        model: str = None,
        temperature: float = None,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None,
    ) -> str:
        """Call OpenAI-compatible API (OpenAI, Nous, vLLM, etc.)."""
        model = model or config.MODEL
        temperature = temperature if temperature is not None else config.TEMPERATURE

        base_url, headers = await self._get_openai_headers()

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

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

            # OpenAI response format
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

    async def _get_openai_headers(self) -> tuple:
        """Get the base URL and auth headers for OpenAI-format API.

        Returns (base_url, headers_dict)
        """
        provider_key = config.LLM_PROVIDER
        provider = PROVIDERS.get(provider_key, PROVIDERS.get("openai"))

        # Mode 1: Direct API key
        if config.LLM_API_KEY:
            base_url = config.LLM_INFERENCE_URL or provider.get(
                "inference_base", "https://api.openai.com/v1"
            )
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

        base_url = config.LLM_INFERENCE_URL or provider.get(
            "inference_base", "https://api.openai.com/v1"
        )
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
