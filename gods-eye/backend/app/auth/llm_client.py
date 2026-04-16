"""Multi-format LLM client with support for OpenAI and Anthropic APIs.

Supports:
  - OpenAI-compatible APIs (/chat/completions) — OpenAI, Nous, vLLM, etc.
  - Anthropic-compatible APIs (/v1/messages) — Anthropic, OpusCode Pro, etc.

Auth modes:
  1. Direct API key (LLM_API_KEY env var) — recommended for OpusCode Pro
  2. Device auth (OAuth tokens from Codex login) — for OpenAI/Nous
"""

import asyncio
import json
import logging
import random
from typing import Optional, Dict, Any, List

import httpx

from app.config import config
from app.auth.device_auth import get_auth_manager, PROVIDERS

logger = logging.getLogger(__name__)

# Retryable upstream HTTP status codes. OpusMax's nginx returns 502 under burst
# load; 503/504 indicate transient upstream unavailability or timeouts.
_RETRY_STATUSES = {429, 502, 503, 504}

# Module-level singleton so ALL LLMClient instances share the same concurrency
# budget. Lazily created on first use so event-loop binding happens inside
# running tasks (avoids "attached to a different loop" in test contexts).
_concurrency_sem: Optional[asyncio.Semaphore] = None


def _get_semaphore() -> asyncio.Semaphore:
    global _concurrency_sem
    if _concurrency_sem is None:
        _concurrency_sem = asyncio.Semaphore(max(1, config.LLM_MAX_CONCURRENT))
    return _concurrency_sem


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
            "stream": True,
            "thinking": {"type": "enabled", "budget_tokens": THINKING_BUDGET},
        }

        if system_parts:
            payload["system"] = "\n\n".join(system_parts)

        url = f"{base_url}/v1/messages"

        # Throttle + retry. Semaphore caps simultaneous requests so OpusMax/nginx
        # doesn't see burst traffic; retry handles transient 502/503/504.
        sem = _get_semaphore()
        max_retries = max(0, config.LLM_MAX_RETRIES)
        base_delay = config.LLM_RETRY_BASE_DELAY
        last_error: Optional[Exception] = None

        async with sem:
            for attempt in range(max_retries + 1):
                try:
                    logger.info(
                        f"Anthropic API call (stream): model={model}, url={url}, "
                        f"msgs={len(user_messages)}, attempt={attempt + 1}/{max_retries + 1}"
                    )

                    # Use streaming to keep the connection alive through
                    # OpusMax's nginx proxy (which has a ~20s idle timeout).
                    # SSE chunks arrive every few seconds, preventing the
                    # proxy from killing the connection before the model
                    # finishes generating.
                    text_parts: List[str] = []
                    current_text = ""
                    got_error = False
                    error_status = 0

                    async with self._http.stream(
                        "POST", url, json=payload, headers=headers
                    ) as stream:
                        # Check for non-2xx before consuming body
                        if stream.status_code == 401:
                            await stream.aread()
                            error_body = stream.text
                            logger.error(f"Anthropic API auth error 401: {error_body}")
                            raise RuntimeError(f"Anthropic API auth error: {error_body}")

                        if stream.status_code in _RETRY_STATUSES and attempt < max_retries:
                            delay = base_delay * (2 ** attempt)
                            delay *= 0.75 + random.random() * 0.5
                            logger.warning(
                                f"Anthropic API {stream.status_code}, retrying in "
                                f"{delay:.2f}s (attempt {attempt + 1}/{max_retries + 1})"
                            )
                            got_error = True
                            error_status = stream.status_code

                        if stream.status_code >= 400 and not got_error:
                            await stream.aread()
                            error_body = stream.text
                            logger.error(f"Anthropic API error {stream.status_code}: {error_body}")
                            raise RuntimeError(f"Anthropic API error {stream.status_code}: {error_body}")

                        if not got_error:
                            # Consume SSE stream, extracting text deltas
                            async for raw_line in stream.aiter_lines():
                                line = raw_line.strip()
                                if not line or not line.startswith("data: "):
                                    continue
                                data_str = line[6:]
                                if data_str == "[DONE]":
                                    break
                                try:
                                    evt = json.loads(data_str)
                                except json.JSONDecodeError:
                                    continue
                                evt_type = evt.get("type", "")
                                if evt_type == "content_block_start":
                                    block = evt.get("content_block", {})
                                    if block.get("type") == "text":
                                        current_text = block.get("text", "")
                                elif evt_type == "content_block_delta":
                                    delta = evt.get("delta", {})
                                    if delta.get("type") == "text_delta":
                                        current_text += delta.get("text", "")
                                elif evt_type == "content_block_stop":
                                    if current_text:
                                        text_parts.append(current_text)
                                        current_text = ""

                    if got_error:
                        await asyncio.sleep(delay)
                        continue

                    # Flush any remaining text
                    if current_text:
                        text_parts.append(current_text)

                    if not text_parts:
                        raise RuntimeError(f"No text content in Anthropic streaming response")

                    result = "\n".join(text_parts)
                    logger.info(
                        f"Anthropic API success (stream): {len(result)} chars, "
                        f"model={model}, attempt={attempt + 1}"
                    )
                    return result

                except httpx.HTTPStatusError as e:
                    error_body = e.response.text
                    logger.error(f"Anthropic API error {e.response.status_code}: {error_body}")
                    last_error = RuntimeError(f"Anthropic API error: {error_body}")
                    if e.response.status_code not in _RETRY_STATUSES or attempt >= max_retries:
                        raise last_error
                    delay = base_delay * (2 ** attempt) * (0.75 + random.random() * 0.5)
                    await asyncio.sleep(delay)
                except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError) as e:
                    logger.warning(
                        f"Network error (retryable) calling Anthropic API: {e} "
                        f"(attempt {attempt + 1}/{max_retries + 1})"
                    )
                    last_error = RuntimeError(f"Network error: {e}")
                    if attempt >= max_retries:
                        raise last_error
                    delay = base_delay * (2 ** attempt) * (0.75 + random.random() * 0.5)
                    await asyncio.sleep(delay)
                except httpx.HTTPError as e:
                    logger.error(f"Network error calling Anthropic API: {e}")
                    raise RuntimeError(f"Network error: {e}")

            if last_error is not None:
                raise last_error
            raise RuntimeError("Anthropic API: exhausted retries with no response")

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
