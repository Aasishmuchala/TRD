#!/bin/bash
# LLM — OpenRouter with Kimi K2.5
export LLM_API_KEY="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"
export LLM_INFERENCE_URL="https://openrouter.ai/api/v1"
export GODS_EYE_MODEL="moonshotai/kimi-k2.5"
export GODS_EYE_LLM_PROVIDER="openai"
export GODS_EYE_MOCK="false"

# Dhan — Market Data API
export DHAN_ACCESS_TOKEN="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJwX2lwIjoiIiwic19pcCI6IiIsImlzcyI6ImRoYW4iLCJwYXJ0bmVySWQiOiIiLCJleHAiOjE3NzUwMjA5MjMsImlhdCI6MTc3NDkzNDUyMywidG9rZW5Db25zdW1lclR5cGUiOiJTRUxGIiwid2ViaG9va1VybCI6Imh0dHA6Ly9sb2NhbGhvc3Q6ODAwMC9hcGkvZGhhbi9wb3N0YmFjayIsImRoYW5DbGllbnRJZCI6IjExMTEwNTk1NzgifQ.htKTAUsH1tnvIuT0luT9qXsX2G2oQdWfge03rk8AlOTK1H4q-tHt0-KWqo4b-tkzi5kUvZw_T253VJ2WQvJlbQ"
export DHAN_CLIENT_ID="1111059578"

cd "$(dirname "$0")"
source venv/bin/activate
exec python run.py
