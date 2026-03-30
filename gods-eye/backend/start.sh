#!/bin/bash
# LLM — OpenRouter with Kimi K2.5
export LLM_API_KEY="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"
export LLM_INFERENCE_URL="https://openrouter.ai/api/v1"
export GODS_EYE_MODEL="moonshotai/kimi-k2.5"
export GODS_EYE_LLM_PROVIDER="openai"
export GODS_EYE_MOCK="false"

# Dhan — Market Data API
export DHAN_ACCESS_TOKEN="53a29ad5-b2a8-426d-bede-5bad2939b161"
export DHAN_CLIENT_ID="b8eae97f"

cd "$(dirname "$0")"
source venv/bin/activate
exec python run.py
