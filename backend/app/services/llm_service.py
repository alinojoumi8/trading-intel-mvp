"""
MiniMax LLM Service — Anthropic-compatible subscription API
Uses the same endpoint that Hermes uses: https://api.minimax.io/anthropic/v1/messages
This is the token-subscription endpoint — no out-of-pocket cost.
"""
import asyncio
import logging
import time
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Endpoint: Anthropic-compatible subscription API (how Hermes connects)
MINIMAX_BASE_URL = "https://api.minimax.io/anthropic"
MINIMAX_API_PATH = "/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

# Retry configuration
MAX_RETRIES = 3
BASE_DELAY = 2.0
TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def _build_messages(prompt: str, system_prompt: Optional[str] = None) -> list[dict]:
    """Build messages array for Anthropic API.

    Uses inline [System: ...] wrapper for MiniMax compatibility —
    this ensures MiniMax emits a text block alongside thinking blocks.
    """
    if system_prompt:
        content = f"[System: {system_prompt}]\n\n{prompt}"
    else:
        content = prompt
    return [{"role": "user", "content": content}]


async def _call_minimax_with_retry(
    messages: list[dict],
    temperature: float,
    max_tokens: int,
) -> dict:
    """
    Call MiniMax Anthropic-compatible subscription API.
    Endpoint: POST https://api.minimax.io/anthropic/v1/messages
    """
    url = f"{MINIMAX_BASE_URL}{MINIMAX_API_PATH}"
    api_key = settings.MINIMAX_API_KEY

    headers = {
        "Authorization": f"Bearer {api_key}",
        "x-api-key": api_key,
        "Content-Type": "application/json",
        "anthropic-version": ANTHROPIC_VERSION,
    }

    # Last message becomes the prompt; model comes from config
    user_message = messages[-1]["content"]
    payload = {
        "model": settings.MINIMAX_MODEL,
        "messages": [{"role": "user", "content": user_message}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                logger.info(
                    f"[MiniMax] API call attempt {attempt + 1}/{MAX_RETRIES} "
                    f"(model={settings.MINIMAX_MODEL})"
                )
                response = await client.post(url, json=payload, headers=headers)

                if response.status_code == 429:
                    err_body = response.text.lower()
                    if "balance" in err_body or "quota" in err_body or "insufficient" in err_body:
                        raise Exception(f"[MiniMax] Billing exhausted: {response.text[:200]}")
                    delay = BASE_DELAY * (2 ** attempt)
                    logger.warning(f"[MiniMax] Rate limited, retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)
                    continue

                if response.status_code in TRANSIENT_STATUS_CODES:
                    delay = BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        f"[MiniMax] HTTP {response.status_code}, retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                    continue

                response.raise_for_status()
                return response.json()

        except httpx.TimeoutException as e:
            last_error = f"Timeout: {e}"
            delay = BASE_DELAY * (2 ** attempt)
            logger.warning(f"[MiniMax] Timeout, retrying in {delay:.1f}s...")
            await asyncio.sleep(delay)
        except httpx.HTTPStatusError as e:
            err_body = e.response.text
            if e.response.status_code == 429:
                if "balance" in err_body.lower() or "quota" in err_body.lower():
                    raise Exception(f"[MiniMax] Billing exhausted: {err_body[:200]}")
            last_error = f"HTTP {e.response.status_code}: {err_body[:200]}"
            delay = BASE_DELAY * (2 ** attempt)
            logger.warning(f"[MiniMax] Error {e.response.status_code}, retrying in {delay:.1f}s...")
            await asyncio.sleep(delay)
        except Exception as e:
            last_error = str(e)
            delay = BASE_DELAY * (2 ** attempt)
            logger.warning(f"[MiniMax] Error: {e}, retrying in {delay:.1f}s...")
            await asyncio.sleep(delay)

    raise Exception(f"[MiniMax] Failed after {MAX_RETRIES} attempts: {last_error}")


async def generate(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2000,
) -> str:
    """
    Generate text from MiniMax LLM via Anthropic subscription API.

    Args:
        prompt: The user prompt.
        system_prompt: Optional system prompt.
        temperature: Sampling temperature (0.0–2.0).
        max_tokens: Max tokens to generate.

    Returns:
        Generated text content string.

    Raises:
        Exception: If the API call fails.
    """
    messages = _build_messages(prompt, system_prompt)

    logger.info(
        f"[MiniMax] generate: model={settings.MINIMAX_MODEL}, "
        f"temperature={temperature}, max_tokens={max_tokens}"
    )

    start = time.monotonic()

    try:
        response_data = await _call_minimax_with_retry(messages, temperature, max_tokens)
    except Exception as e:
        raise Exception(f"MiniMax generation failed: {e}")

    elapsed = time.monotonic() - start

    # Parse Anthropic response format
    try:
        content_blocks = response_data.get("content", [])
        if not content_blocks:
            raise Exception("No content blocks returned from MiniMax")

        # Extract text from response
        text_parts = []
        thinking_parts = []
        for block in content_blocks:
            block_type = block.get("type", "")
            if block_type == "text":
                text_parts.append(block.get("text", ""))
            elif block_type in ("thinking", "thinking_block"):
                thinking_parts.append(block.get("thinking", block.get("thought", "")))

        logger.info(f"[LLM] MiniMax response: {len(content_blocks)} blocks, {len(text_parts)} text, {len(thinking_parts)} thinking")
        logger.debug(f"[LLM] Response blocks: {content_blocks}")

        # Fallback: extract JSON from thinking blocks (MiniMax returns JSON inside thinking on complex prompts)
        if not text_parts and thinking_parts:
            import re, json as _json
            for tb in thinking_parts:
                # Try direct json.loads first
                try:
                    parsed = _json.loads(tb.strip())
                    text_parts = [tb.strip()]
                    logger.info("[LLM] Parsed thinking block as full JSON")
                    break
                except Exception:
                    pass
                # Try extracting JSON objects with balanced braces
                try:
                    # Find the first { and try to parse progressively to find valid JSON
                    start = tb.find('{')
                    if start >= 0:
                        # Try different end positions to find valid JSON
                        for end in range(len(tb), start, -1):
                            try:
                                candidate = tb[start:end].strip()
                                parsed = _json.loads(candidate)
                                text_parts = [candidate]
                                logger.info(f"[LLM] Extracted JSON from thinking block ({end - start} chars)")
                                break
                            except Exception:
                                continue
                except Exception:
                    pass

        if not text_parts:
            logger.warning(f"[LLM] No text content. Thinking blocks: {thinking_parts[:2]}")
            raise Exception("No text content returned from MiniMax")

        # Also check thinking blocks for complete JSON if text content looks truncated
        content = "\n".join(text_parts)
        if content and not content.strip().endswith("}"):
            # Text content appears truncated — check thinking blocks for complete JSON
            for tb in thinking_parts:
                try:
                    start = tb.find("{")
                    if start >= 0:
                        for end in range(len(tb), start, -1):
                            try:
                                candidate = tb[start:end].strip()
                                _json.loads(candidate)
                                # Valid JSON found in thinking block
                                content = candidate
                                text_parts = [candidate]
                                logger.info(f"[LLM] Recovered complete JSON from thinking block ({end - start} chars)")
                                break
                            except Exception:
                                continue
                except Exception:
                    pass
                if text_parts:
                    break
        logger.info(f"[MiniMax] generate completed: {len(content)} chars in {elapsed:.2f}s")
        return content

    except (KeyError, IndexError, TypeError) as e:
        raise Exception(f"Failed to parse MiniMax response: {e} — {response_data}")


# Synchronous wrapper
def generate_sync(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 4000,
) -> str:
    """Synchronous wrapper — use when calling from sync code."""
    return asyncio.run(generate(prompt, system_prompt, temperature, max_tokens))
