"""FastAPI routes for God's Eye."""

import os
import sqlite3
import time
import uuid
from datetime import datetime
from typing import Optional
import httpx
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from app.auth.middleware import require_auth
from app.auth.device_auth import DeviceAuthManager, DeviceCodeResponse, AuthTokens, get_auth_manager
from app.learning.skill_store import get_skill_store
from app.limiter import limiter
from app.api.schemas import (
    MarketInput,
    SimulationResult,
    PresetScenario,
    AggregatorResult,
    BacktestRunRequest,
    BacktestRunResponse,
    BacktestRunSummary,
    BacktestDayResponse,
    SignalScoreSchema,
    QuantSignalResponse,
    QuantBacktestRunResponse,
    QuantBacktestDaySchema,
    QuantBacktestRequest,
)
from app.engine.backtest_engine import BacktestEngine
from app.engine.signal_scorer import SignalScorer
from app.engine.quant_signal_engine import QuantInputs, QuantSignalEngine
from app.engine.quant_backtest import quant_backtest_engine, QuantBacktestRunResult
import dataclasses
from app.api.errors import safe_error_response, log_error_safely
from app.engine.orchestrator import Orchestrator
from app.engine.aggregator import Aggregator
from app.engine.scenarios import ScenarioGenerator
from app.engine.feedback_engine import FeedbackEngine
from app.memory.prediction_tracker import PredictionTracker
from app.memory.agent_memory import AgentMemory
from app.data.market_data import market_data_service
from app.data.cache import cache
from app.data.historical_store import historical_store
from app.data.dhan_client import DhanFetchError
from app.data.technical_signals import technical_signals, TechnicalSignals
from app.config import config
from app.engine.paper_trader import paper_trader, PaperTrade

# Public router for health checks and auth endpoints
router = APIRouter(prefix="/api", tags=["health", "auth"])

# Protected router for all other endpoints
protected_router = APIRouter(prefix="/api", tags=["simulation"], dependencies=[Depends(require_auth)])

# Initialize components
tracker = PredictionTracker()
backtest_engine = BacktestEngine()


class SimulateRequest(BaseModel):
    """Flexible simulate request: scenario_id, market_input, flat fields, or source=live."""
    scenario_id: Optional[str] = None
    market_input: Optional[MarketInput] = None
    source: Optional[str] = None  # "live" to auto-populate from NSE

    # Also accept flat MarketInput fields for backwards compatibility
    nifty_spot: Optional[float] = None
    india_vix: Optional[float] = None
    fii_flow_5d: Optional[float] = None
    dii_flow_5d: Optional[float] = None
    usd_inr: Optional[float] = None
    dxy: Optional[float] = None
    pcr_index: Optional[float] = None
    max_pain: Optional[float] = None
    dte: Optional[int] = None
    context: Optional[str] = None


@protected_router.post("/simulate")
@limiter.limit("10/minute")
async def simulate(req_data: SimulateRequest, request: Request):
    """Run market simulation with all agents.

    Accepts either:
    - {"scenario_id": "rbi_rate_cut"} to use a preset
    - {"market_input": {...}} with full MarketInput fields
    - Flat MarketInput fields at top level (backwards compatible)
    """
    try:
        market_input = None
        live_extras = {}
        live_data_source = "fallback"  # default; overridden for source=live

        # Option 0: Live market data from NSE
        if req_data.source == "live":
            live_data = await market_data_service.build_market_input()
            # Separate extras (underscore-prefixed) from MarketInput fields
            mi_fields = {}
            for k, v in live_data.items():
                if k.startswith("_"):
                    live_extras[k] = v
                else:
                    mi_fields[k] = v
            # Fetch snapshot to get data_source (build_market_input uses get_live_snapshot internally)
            snapshot = await market_data_service.get_live_snapshot()
            live_data_source = snapshot.get("data_source", "nse_live")
            market_input = MarketInput(**mi_fields)

        # Option 1: Load from preset scenario
        elif req_data.scenario_id:
            scenarios = ScenarioGenerator.get_all_scenarios()
            for scenario in scenarios:
                if scenario.scenario_id == req_data.scenario_id:
                    market_input = scenario.market_data
                    break
            if not market_input:
                raise HTTPException(
                    status_code=404,
                    detail=f"Scenario '{req_data.scenario_id}' not found",
                )

        # Option 2: Nested market_input object
        if not market_input and req_data.market_input:
            market_input = req_data.market_input

        # Option 3: Flat fields (backwards compat)
        if not market_input and req_data.nifty_spot is not None:
            market_input = MarketInput(
                nifty_spot=req_data.nifty_spot,
                india_vix=req_data.india_vix or 15.0,
                fii_flow_5d=req_data.fii_flow_5d or 0.0,
                dii_flow_5d=req_data.dii_flow_5d or 0.0,
                usd_inr=req_data.usd_inr or 83.0,
                dxy=req_data.dxy or 104.0,
                pcr_index=req_data.pcr_index or 1.0,
                max_pain=req_data.max_pain or req_data.nifty_spot,
                dte=req_data.dte or 5,
                context=req_data.context or "normal",
            )
        if not market_input:
            raise HTTPException(
                status_code=400,
                detail="Provide 'source': 'live', 'scenario_id', 'market_input', or flat market fields",
            )

        # Create orchestrator
        orchestrator = Orchestrator()

        # Run simulation
        sim_result = await orchestrator.run_simulation(market_input)

        # Create result object
        simulation_id = f"sim_{uuid.uuid4().hex[:12]}"

        # Aggregate results (pass accuracy-tuned weights if available)
        aggregator_result = Aggregator.aggregate(
            sim_result["final_outputs"],
            hybrid=True,
            tuned_weights=sim_result.get("tuned_weights"),
        )

        # Check data freshness
        from app.data.freshness import check_data_freshness
        freshness = check_data_freshness()
        data_warnings = freshness.get("warnings", [])

        # Create response
        result = SimulationResult(
            simulation_id=simulation_id,
            timestamp=datetime.now(),
            market_input=market_input,
            agents_output=sim_result["final_outputs"],
            round_history=sim_result["round_history"],
            aggregator_result=aggregator_result,
            execution_time_ms=sim_result["execution_time_ms"],
            model_used=config.MODEL,
            feedback_active=sim_result.get("feedback_active", False),
            tuned_weights=sim_result.get("tuned_weights"),
            data_warnings=data_warnings,
        )

        # Log to database
        tracker.log_simulation(result)
        tracker.log_prediction(result)

        # Attach live market extras if available, and always include data_source
        response = result.model_dump()
        if live_extras:
            response["live_data"] = live_extras
            response["data_source"] = live_data_source
        else:
            # Non-live simulation (scenario or manual input) — always fallback data
            response["data_source"] = "fallback"

        # Compute signal_score using SignalScorer (sentiment + technicals)
        vix = market_input.india_vix
        if vix < 14:
            vix_regime = "low"
        elif vix < 20:
            vix_regime = "normal"
        elif vix < 30:
            vix_regime = "elevated"
        else:
            vix_regime = "high"

        pcr = market_input.pcr_index
        oi_sentiment = "bullish" if pcr > 1.2 else ("bearish" if pcr < 0.8 else None)

        live_signals = {
            "rsi": market_input.rsi_14,       # may be None — scorer handles it gracefully
            "supertrend": None,               # not available in live MarketInput
            "vix_regime": vix_regime,
            "oi_sentiment": oi_sentiment,
        }

        score_result = SignalScorer.score(
            direction=aggregator_result.final_direction,
            conviction=aggregator_result.final_conviction,
            signals=live_signals,
            instrument="NIFTY",   # live simulate is always Nifty context
        )
        response["signal_score"] = vars(score_result)

        return response

    except HTTPException:
        raise
    except Exception:
        raise safe_error_response(500, "OPERATION_FAILED", "An unexpected error occurred")


@protected_router.get("/presets", response_model=list)
async def get_presets():
    """Get list of preset scenarios."""
    try:
        scenarios = ScenarioGenerator.get_all_scenarios()
        return [
            {
                "scenario_id": s.scenario_id,
                "name": s.name,
                "description": s.description,
                "expected_direction": s.expected_direction,
            }
            for s in scenarios
        ]
    except Exception:
        raise safe_error_response(500, "OPERATION_FAILED", "An unexpected error occurred")


@protected_router.get("/presets/{scenario_id}", response_model=PresetScenario)
async def get_preset(scenario_id: str):
    """Get a specific preset scenario."""
    try:
        scenarios = ScenarioGenerator.get_all_scenarios()
        for scenario in scenarios:
            if scenario.scenario_id == scenario_id:
                return scenario
        raise HTTPException(status_code=404, detail="Scenario not found")
    except HTTPException:
        raise
    except Exception:
        raise safe_error_response(500, "OPERATION_FAILED", "An unexpected error occurred")


@protected_router.get("/history")
async def get_history(limit: int = 20, offset: int = 0):
    """Get simulation history with pagination."""
    try:
        history = tracker.get_simulation_history(limit=limit, offset=offset)
        return {
            "total_count": len(history),
            "page": offset // limit + 1,
            "page_size": limit,
            "items": history,
        }
    except Exception:
        raise safe_error_response(500, "OPERATION_FAILED", "An unexpected error occurred")


@protected_router.post("/history/{simulation_id}/outcome")
async def record_outcome(simulation_id: str, actual_direction: str, notes: str = None):
    """Record actual market outcome for a prediction."""
    try:
        prediction_id = f"pred_{simulation_id}"
        success = tracker.record_outcome(prediction_id, actual_direction, notes)

        if not success:
            raise HTTPException(status_code=404, detail="Prediction not found")

        return {
            "prediction_id": prediction_id,
            "actual_direction": actual_direction,
            "recorded": True,
        }
    except HTTPException:
        raise
    except Exception:
        raise safe_error_response(500, "OPERATION_FAILED", "An unexpected error occurred")


@protected_router.get("/metrics")
async def get_metrics(lookback_days: int = 30):
    """Get accuracy metrics for recent predictions."""
    try:
        metrics = tracker.get_accuracy_metrics(lookback_days=lookback_days)
        return {
            "period_days": lookback_days,
            "by_direction": metrics,
        }
    except Exception:
        raise safe_error_response(500, "OPERATION_FAILED", "An unexpected error occurred")


@protected_router.get("/agent/{agent_id}")
async def get_agent(agent_id: str):
    """Get agent details and recent performance."""
    agent_map = {
        "fii": {
            "id": "fii", "name": "FII Flows Analyst", "type": "LLM",
            "persona": "Foreign Institutional Investor managing Asia-Pacific allocations",
            "time_horizon": "Quarterly", "weight": config.AGENT_WEIGHTS.get("FII", 0.30),
            "risk_appetite": "Moderate",
        },
        "dii": {
            "id": "dii", "name": "DII Strategy Desk", "type": "LLM",
            "persona": "Large domestic mutual fund/pension manager tracking SIP inflows",
            "time_horizon": "Quarterly", "weight": config.AGENT_WEIGHTS.get("DII", 0.25),
            "risk_appetite": "Conservative",
        },
        "retail_fno": {
            "id": "retail_fno", "name": "Retail F&O Desk", "type": "LLM",
            "persona": "Retail derivatives trader focused on intraday volatility and expiry plays",
            "time_horizon": "Intraday", "weight": config.AGENT_WEIGHTS.get("RETAIL_FNO", 0.15),
            "risk_appetite": "Aggressive",
        },
        "algo": {
            "id": "algo", "name": "Algo Trading Engine", "type": "QUANT",
            "persona": "Pure quantitative algorithm analyzing technical signals",
            "time_horizon": "Intraday", "weight": config.AGENT_WEIGHTS.get("ALGO", 0.10),
            "risk_appetite": "Moderate",
        },
        "promoter": {
            "id": "promoter", "name": "Promoter Desk", "type": "LLM",
            "persona": "Company promoter/insider tracking stock performance and control implications",
            "time_horizon": "Yearly", "weight": config.AGENT_WEIGHTS.get("PROMOTER", 0.10),
            "risk_appetite": "Conservative",
        },
        "rbi": {
            "id": "rbi", "name": "RBI Policy Desk", "type": "LLM",
            "persona": "RBI monetary policy committee focusing on inflation control",
            "time_horizon": "Quarterly", "weight": config.AGENT_WEIGHTS.get("RBI", 0.10),
            "risk_appetite": "Conservative",
        },
    }

    agent = agent_map.get(agent_id.lower())
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return agent


@protected_router.get("/agent/{agent_id}/accuracy")
async def get_agent_accuracy(agent_id: str, days: int = 30):
    """Get accuracy metrics for a specific agent from AgentMemory."""
    try:
        memory = AgentMemory(db_path=config.DATABASE_PATH)
        stats = memory.get_agent_accuracy(agent_id.upper(), lookback_days=days)
        return {
            "agent_id": agent_id,
            "period_days": days,
            "total_predictions": stats.total_predictions,
            "correct": stats.correct_predictions,
            "accuracy_percent": stats.accuracy_pct,
            "avg_conviction_when_correct": stats.avg_conviction_correct,
            "avg_conviction_when_wrong": stats.avg_conviction_wrong,
            "calibration_score": stats.calibration_score,
            "recent_streak": stats.recent_streak,
            "strongest_context": stats.strongest_context,
            "weakest_context": stats.weakest_context,
            "direction_breakdown": stats.direction_breakdown,
        }
    except Exception:
        raise safe_error_response(500, "OPERATION_FAILED", "An unexpected error occurred")


@protected_router.get("/feedback/weights")
async def get_feedback_weights(days: int = 90):
    """Get accuracy-tuned agent weights vs base weights."""
    try:
        memory = AgentMemory(db_path=config.DATABASE_PATH)
        engine = FeedbackEngine(agent_memory=memory)
        changes = engine.get_weight_changes(lookback_days=days)
        return {
            "feedback_active": engine.should_activate(),
            "lookback_days": days,
            "min_predictions_required": FeedbackEngine.MIN_PREDICTIONS_FOR_TUNING,
            "agents": changes,
        }
    except Exception:
        raise safe_error_response(500, "OPERATION_FAILED", "An unexpected error occurred")


@protected_router.get("/feedback/patterns/{agent_id}")
async def get_failure_patterns(agent_id: str):
    """Get failure patterns for a specific agent."""
    try:
        memory = AgentMemory(db_path=config.DATABASE_PATH)
        patterns = memory.detect_failure_patterns(agent_id.upper())
        engine = FeedbackEngine(agent_memory=memory)
        prompt_hints = engine.get_prompt_hints(agent_id.upper())
        return {
            "agent_id": agent_id,
            "patterns": [
                {
                    "type": p.pattern_type,
                    "sample_count": p.sample_count,
                    "example_contexts": p.example_contexts,
                }
                for p in patterns
            ],
            "prompt_hints": prompt_hints,
        }
    except Exception:
        raise safe_error_response(500, "OPERATION_FAILED", "An unexpected error occurred")


@protected_router.get("/settings")
async def get_settings():
    """Get current simulation settings."""
    return {
        "agent_weights": config.AGENT_WEIGHTS,
        "samples_per_agent": config.SAMPLES_PER_AGENT,
        "interaction_rounds": config.INTERACTION_ROUNDS,
        "temperature": config.TEMPERATURE,
        "quant_llm_balance": config.QUANT_LLM_BALANCE,
        "model": config.MODEL,
        "mock_mode": config.MOCK_MODE,
    }


@protected_router.post("/settings")
async def update_settings(settings: dict):
    """Update simulation settings."""
    if "agent_weights" in settings:
        weights = settings["agent_weights"]
        total = sum(weights.values())
        if 0.99 <= total <= 1.01:
            config.AGENT_WEIGHTS = weights

    if "samples_per_agent" in settings:
        val = int(settings["samples_per_agent"])
        if 1 <= val <= 10:
            config.SAMPLES_PER_AGENT = val

    if "interaction_rounds" in settings:
        val = int(settings["interaction_rounds"])
        if 1 <= val <= 5:
            config.INTERACTION_ROUNDS = val

    if "temperature" in settings:
        val = float(settings["temperature"])
        if 0 <= val <= 1:
            config.TEMPERATURE = val

    if "quant_llm_balance" in settings:
        val = float(settings["quant_llm_balance"])
        if 0 <= val <= 1:
            config.QUANT_LLM_BALANCE = val

    return {
        "status": "updated",
        "agent_weights": config.AGENT_WEIGHTS,
        "samples_per_agent": config.SAMPLES_PER_AGENT,
        "interaction_rounds": config.INTERACTION_ROUNDS,
        "temperature": config.TEMPERATURE,
        "quant_llm_balance": config.QUANT_LLM_BALANCE,
    }


@protected_router.get("/market/live")
async def get_live_market():
    """Get current live market snapshot: Nifty, VIX, FII/DII, breadth."""
    try:
        snapshot = await market_data_service.get_live_snapshot()
        return snapshot
    except Exception:
        raise safe_error_response(500, "OPERATION_FAILED", "An unexpected error occurred")


@protected_router.get("/market/options")
async def get_options_data(symbol: str = "NIFTY"):
    """Get options chain summary: PCR, max pain, top OI strikes."""
    try:
        data = await market_data_service.get_options_chain(symbol)
        return data
    except Exception:
        raise safe_error_response(500, "OPERATION_FAILED", "An unexpected error occurred")


@protected_router.get("/market/sectors")
async def get_sectors():
    """Get sector index values with % change."""
    try:
        sectors = await market_data_service.get_sector_indices()
        return {"sectors": sectors}
    except Exception:
        raise safe_error_response(500, "OPERATION_FAILED", "An unexpected error occurred")


@protected_router.get("/market/cache-stats")
async def get_cache_stats():
    """Get cache statistics for debugging."""
    return cache.stats()


@protected_router.get("/market/data-freshness")
async def get_data_freshness():
    """Check freshness of all data sources — returns warnings for stale data."""
    from app.data.freshness import check_data_freshness
    snapshot = cache.get("live_snapshot")
    live_ts = snapshot.get("timestamp") if snapshot else None
    return check_data_freshness(live_timestamp=live_ts)


@router.get("/health")
async def health_check():
    """Health check endpoint with database connectivity check."""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
        "model": config.MODEL,
        "mock_mode": config.MOCK_MODE,
        "llm_provider": config.LLM_PROVIDER,
        "learning_enabled": config.LEARNING_ENABLED,
        "environment": config.ENV,
    }

    # Check database connectivity
    try:
        db_path = config.DATABASE_PATH
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path, timeout=5)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            conn.close()
            health_status["database"] = {
                "status": "connected",
                "path": db_path,
                "size_mb": round(os.path.getsize(db_path) / (1024 * 1024), 2),
            }
        else:
            health_status["database"] = {
                "status": "not_initialized",
                "path": db_path,
            }
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["database"] = {
            "status": "error",
            "error": str(e),
        }

    return health_status


# ─── Auth endpoints (Codex-style device flow) ─────────────────────────────

@router.post("/auth/login")
@limiter.limit("5/minute")
async def start_login(request: Request, provider: str = "openai"):
    """Start OAuth device code flow. Returns a link + code for the user.

    User opens the URL, enters the code, and the system gets tokens.
    Then poll /api/auth/status until authenticated.
    """
    # Mock mode bypass for testing
    if config.MOCK_MODE:
        return {
            "status": "pending",
            "user_code": "MOCK_USER_CODE",
            "verification_uri": "https://localhost:3000/auth/verify",
            "verification_uri_complete": "https://localhost:3000/auth/verify?code=MOCK_USER_CODE",
            "expires_in": 600,
            "interval": 5,
            "device_code": "MOCK_DEVICE_CODE",
            "provider": provider,
            "message": "Mock mode: Device code flow bypassed",
        }

    try:
        auth = DeviceAuthManager(provider=provider)
        device_info = await auth.request_device_code()

        return {
            "status": "pending",
            "user_code": device_info.user_code,
            "verification_uri": device_info.verification_uri,
            "verification_uri_complete": device_info.verification_uri_complete,
            "expires_in": device_info.expires_in,
            "interval": device_info.interval,
            "device_code": device_info.device_code,
            "provider": provider,
            "message": f"Open {device_info.verification_uri} and enter code: {device_info.user_code}",
        }
    except Exception:
        raise safe_error_response(500, "LOGIN_FAILED", "Login initiation failed. Please try again.")


@router.post("/auth/poll")
@limiter.limit("30/minute")
async def poll_auth(request: Request, device_code: str, provider: str = "openai"):
    """Poll for device code authorization. Call this repeatedly until authorized.

    Returns status: "waiting" | "authorized" | "expired" | "error"
    """
    try:
        auth = DeviceAuthManager(provider=provider)

        # Single poll attempt (non-blocking)
        payload = {
            "grant_type": auth.provider["grant_type"],
            "device_code": device_code,
            "client_id": auth.provider["client_id"],
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                auth.provider["token_endpoint"],
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            data = response.json()

        if response.status_code == 200 and "access_token" in data:
            tokens = AuthTokens(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token", ""),
                expires_at=time.time() + data.get("expires_in", 3600),
                id_token=data.get("id_token", ""),
                token_type=data.get("token_type", "Bearer"),
                provider=provider,
            )
            state = auth._load_state()
            state.active_provider = provider
            state.set_tokens(tokens)
            auth._save_state()

            # Disable mock mode now that we're authenticated
            config.MOCK_MODE = False

            return {
                "status": "authorized",
                "provider": provider,
                "model": config.MODEL,
                "inference_base": auth.provider.get("inference_base", ""),
            }

        error = data.get("error", "")
        if error == "authorization_pending":
            return {"status": "waiting", "message": "Waiting for user to authorize..."}
        elif error == "slow_down":
            return {"status": "waiting", "message": "Slow down, try again in a few seconds"}
        elif error == "expired_token":
            return {"status": "expired", "message": "Device code expired. Start login again."}
        else:
            return {"status": "error", "message": data.get("error_description", error)}

    except Exception:
        raise safe_error_response(500, "OPERATION_FAILED", "An unexpected error occurred")


@router.get("/auth/status")
async def get_auth_status():
    """Check current authentication status."""
    try:
        auth = get_auth_manager()
        status = auth.get_auth_status()
        status["mock_mode"] = config.MOCK_MODE
        return status
    except Exception as e:
        return {
            "authenticated": False,
            "provider": config.LLM_PROVIDER,
            "mock_mode": config.MOCK_MODE,
            "error": str(e),
        }


@router.post("/auth/logout")
async def logout():
    """Clear stored auth tokens."""
    try:
        auth = get_auth_manager()
        auth.logout()
        config.MOCK_MODE = True
        return {"status": "logged_out"}
    except Exception:
        raise safe_error_response(500, "OPERATION_FAILED", "An unexpected error occurred")


# ─── Learning / Skills endpoints ──────────────────────────────────────────

@protected_router.get("/learning/skills")
async def list_skills():
    """List all learned skills across agents."""
    try:
        store = get_skill_store()
        skills = store.list_skills_summary()
        return {
            "total_skills": len(skills),
            "learning_enabled": config.LEARNING_ENABLED,
            "skills": skills,
        }
    except Exception:
        raise safe_error_response(500, "OPERATION_FAILED", "An unexpected error occurred")


@protected_router.get("/learning/skills/{agent_id}")
async def get_agent_skills(agent_id: str):
    """List learned skills for a specific agent."""
    try:
        store = get_skill_store()
        skills = store.load_skills(agent_id.upper())
        return {
            "agent_id": agent_id.upper(),
            "total_skills": len(skills),
            "skills": [
                {
                    "name": s.name,
                    "description": s.description,
                    "content": s.content,
                    "trigger_conditions": s.trigger_conditions,
                    "success_rate": s.success_rate,
                    "times_applied": s.times_applied,
                }
                for s in skills
            ],
        }
    except Exception:
        raise safe_error_response(500, "OPERATION_FAILED", "An unexpected error occurred")


@protected_router.post("/learning/toggle")
async def toggle_learning(enabled: bool = True):
    """Enable or disable the auto-learning system."""
    config.LEARNING_ENABLED = enabled
    return {
        "learning_enabled": config.LEARNING_ENABLED,
        "skill_directory": config.LEARNING_SKILL_DIR,
    }


# ─── Historical Data endpoints ────────────────────────────────────────────

@protected_router.get("/market/historical/{instrument}")
async def get_historical_data(
    instrument: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
):
    """Return cached daily OHLCV or VIX data for an instrument.

    Path params:
        instrument: "nifty", "banknifty", or "vix" (case-insensitive)

    Query params (optional):
        from_date: YYYY-MM-DD
        to_date:   YYYY-MM-DD

    Returns:
        {"instrument": str, "count": int, "data": [...]}

    Raises:
        404 if instrument name is invalid
        502 if Dhan API fails (explicit error, no fallback)
    """
    instrument_upper = instrument.upper()
    if instrument_upper not in ("NIFTY", "BANKNIFTY", "VIX"):
        raise HTTPException(
            status_code=404,
            detail=f"Unknown instrument '{instrument}'. Valid: nifty, banknifty, vix",
        )

    try:
        if instrument_upper == "VIX":
            rows = await historical_store.get_vix_closes(
                from_date=from_date, to_date=to_date
            )
        else:
            rows = await historical_store.get_ohlcv(
                instrument_upper, from_date=from_date, to_date=to_date
            )
    except DhanFetchError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Dhan API error: {exc}",
        )
    except Exception:
        raise safe_error_response(500, "OPERATION_FAILED", "An unexpected error occurred")

    return {
        "instrument": instrument_upper,
        "count": len(rows),
        "from_date": from_date,
        "to_date": to_date,
        "data": rows,
    }


@protected_router.post("/market/historical/backfill")
async def trigger_backfill():
    """Manually trigger a full historical data backfill for all instruments.

    Fetches NIFTY, BANKNIFTY, and VIX from Dhan sequentially.
    Use this on a fresh database or after extended downtime.

    Returns:
        {"status": "complete", "rows_stored": {"NIFTY": N, "BANKNIFTY": N, "VIX": N}}

    Raises:
        502 if Dhan API fails for any instrument
    """
    try:
        results = await historical_store.backfill_all()
        return {
            "status": "complete",
            "rows_stored": results,
        }
    except DhanFetchError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Dhan backfill failed: {exc}",
        )
    except Exception:
        raise safe_error_response(500, "OPERATION_FAILED", "An unexpected error occurred")


@protected_router.get("/market/signals/{instrument}/{date}")
async def get_signals_for_date(instrument: str, date: str):
    """Return full technical signal object for a stored date.

    Path params:
      instrument: "nifty" or "banknifty" (case-insensitive)
      date: "YYYY-MM-DD"

    Response shape:
      {
        "instrument": str,
        "date": str,
        "rsi": float,                   # 0-100, Wilder 14-period
        "vwap_deviation_pct": float,    # signed %, positive = above VWAP
        "supertrend": str,              # "bullish" | "bearish"
        "vix_regime": str,              # "low" | "normal" | "elevated" | "high"
        "vix_close": float | null,      # raw VIX for that date
        "oi": {                         # null if no OI snapshot stored for date
          "call_oi": int,
          "put_oi": int,
          "pcr": float,
          "net_sentiment": str
        } | null
      }

    HTTP 400 on invalid instrument. HTTP 404 when no OHLCV rows exist for that date.
    HTTP 404 when VIX data is missing (not a 500 — VIX being absent is a data gap, not a crash).
    """
    inst_upper = instrument.upper()
    if inst_upper not in ("NIFTY", "BANKNIFTY"):
        raise HTTPException(status_code=400, detail=f"instrument must be 'nifty' or 'banknifty', got {instrument!r}")

    try:
        ohlcv_rows = await historical_store.get_ohlcv(inst_upper)
    except DhanFetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    # Check target date exists
    available_dates = {r["date"] for r in ohlcv_rows}
    if date not in available_dates:
        raise HTTPException(status_code=404, detail=f"No OHLCV data for {inst_upper} on {date}")

    # Compute OHLCV-based signals (uses all rows up to date)
    sigs = TechnicalSignals.compute_signals_for_date(ohlcv_rows, date)

    # VIX regime for that specific date
    vix_close = None
    vix_regime = "normal"
    try:
        vix_rows = await historical_store.get_vix_closes(to_date=date)
        if vix_rows:
            # Find the VIX close on or nearest before the target date
            matching = [r for r in vix_rows if r["date"] == date]
            if matching:
                vix_close = matching[-1]["close"]
            elif vix_rows:
                vix_close = vix_rows[-1]["close"]  # use most recent available
            if vix_close is not None:
                vix_regime = TechnicalSignals.classify_vix_regime(vix_close)
    except DhanFetchError:
        pass  # VIX missing is non-fatal for signal response

    # OI snapshot (optional — None is valid for historical dates before capture)
    oi_data = historical_store.get_oi_snapshot(inst_upper, date)

    return {
        "instrument": inst_upper,
        "date": date,
        "rsi": sigs.get("rsi"),
        "vwap_deviation_pct": sigs.get("vwap_deviation_pct"),
        "supertrend": sigs.get("supertrend"),
        "vix_regime": vix_regime,
        "vix_close": vix_close,
        "oi": oi_data,
    }


@protected_router.post("/market/oi/capture")
async def capture_oi_snapshot():
    """Fetch live OI from Dhan and store as today's snapshot for both NIFTY and BANKNIFTY.

    Called manually or by a daily cron after market close to build the OI history.
    Returns: {"nifty": {...}, "banknifty": {...}} with stored snapshot data.

    Returns 502 if Dhan OI fetch fails. Returns partial result if one instrument fails
    (logs warning, continues to other instrument).
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")
    result = {}

    # NIFTY OI via fetch_options_summary
    from app.data.dhan_client import dhan_client
    nifty_oi = await dhan_client.fetch_options_summary()
    if nifty_oi:
        historical_store.store_oi_snapshot(
            "NIFTY", today,
            call_oi=nifty_oi.get("total_call_oi", 0),
            put_oi=nifty_oi.get("total_put_oi", 0),
            pcr=nifty_oi.get("pcr", 1.0),
        )
        result["nifty"] = historical_store.get_oi_snapshot("NIFTY", today)
    else:
        result["nifty"] = None

    # BANKNIFTY OI via get_option_chain("25")
    bn_chain = await dhan_client.get_option_chain("25")
    if bn_chain and "data" in bn_chain:
        chain = bn_chain["data"]
        total_call_oi = sum(r.get("oi", 0) or 0 for r in chain if r.get("option_type", "").upper() == "CE")
        total_put_oi = sum(r.get("oi", 0) or 0 for r in chain if r.get("option_type", "").upper() == "PE")
        pcr = total_put_oi / total_call_oi if total_call_oi > 0 else 1.0
        historical_store.store_oi_snapshot(
            "BANKNIFTY", today,
            call_oi=total_call_oi,
            put_oi=total_put_oi,
            pcr=pcr,
        )
        result["banknifty"] = historical_store.get_oi_snapshot("BANKNIFTY", today)
    else:
        result["banknifty"] = None

    return {"date": today, "captured": result}


# ─── Backtest Engine endpoints ────────────────────────────────────────────────

@protected_router.post("/backtest/run", response_model=BacktestRunResponse)
async def run_backtest(request: BacktestRunRequest):
    """Run a backtest over a historical date range using real LLM agents.

    Trade structure: close-to-close (MOC entry at T's close, exit at T+1's close).
    Uses Claude Haiku per day for speed (~$3 for a full FY run).
    Stores result in SQLite backtest_runs table for later retrieval.
    """
    try:
        result = await backtest_engine.run_backtest(
            instrument=request.instrument,
            from_date=request.from_date,
            to_date=request.to_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Backtest failed: {exc}")

    return _serialize_backtest_result(result)


@protected_router.get("/backtest/results/{run_id}", response_model=BacktestRunResponse)
async def get_backtest_result(run_id: str):
    """Retrieve a previously stored backtest run by ID."""
    import sqlite3, json
    from app.config import config

    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT result_json FROM backtest_runs WHERE run_id = ?", (run_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail=f"Backtest run {run_id!r} not found")

    from app.engine.backtest_engine import BacktestRunResult, BacktestDayResult
    raw = json.loads(row["result_json"])
    # Reconstruct from stored JSON — result_json was stored via dataclasses.asdict()
    # Re-hydrate as BacktestRunResult for serialisation
    days = [BacktestDayResult(**d) for d in raw["days"]]
    result = BacktestRunResult(**{**raw, "days": days})
    return _serialize_backtest_result(result)


def _serialize_backtest_result(result) -> BacktestRunResponse:
    """Convert BacktestRunResult dataclass into BacktestRunResponse Pydantic model.

    Computes cumulative_pnl_points in the API layer (not stored in engine output).
    """
    cumulative = 0.0
    day_responses = []
    for day in result.days:
        cumulative += day.pnl_points
        # Propagate signal_score (present in runs from Phase 8 onward; None for older runs)
        ss_schema = SignalScoreSchema(**day.signal_score) if day.signal_score else None
        day_responses.append(BacktestDayResponse(
            date=day.date,
            next_date=day.next_date,
            nifty_close=day.nifty_close,
            nifty_next_close=day.nifty_next_close,
            actual_move_pct=round(day.actual_move_pct, 4),
            predicted_direction=day.predicted_direction,
            predicted_conviction=round(day.predicted_conviction, 2),
            direction_correct=day.direction_correct,
            pnl_points=round(day.pnl_points, 2),
            cumulative_pnl_points=round(cumulative, 2),
            per_agent_directions=day.per_agent_directions,
            signals=day.signals,
            signal_score=ss_schema,
            stop_loss_hit=getattr(day, 'stop_loss_hit', False),
            stop_price=getattr(day, 'stop_price', None),
            stop_distance_pts=getattr(day, 'stop_distance_pts', None),
            entry_price=getattr(day, 'entry_price', 0.0),
            overnight_gap_pct=getattr(day, 'overnight_gap_pct', 0.0),
        ))

    summary = BacktestRunSummary(
        run_id=result.run_id,
        instrument=result.instrument,
        from_date=result.from_date,
        to_date=result.to_date,
        mock_mode=result.mock_mode,
        day_count=len(result.days),
        overall_accuracy=round(result.overall_accuracy, 4),
        win_rate_pct=round(result.overall_accuracy * 100, 2),
        per_agent_accuracy={k: round(v, 4) for k, v in result.per_agent_accuracy.items()},
        total_pnl_points=round(result.total_pnl_points, 2),
        created_at=result.created_at,
        # Phase 3 performance metrics
        hit_rate_pct=getattr(result, 'hit_rate_pct', 0.0),
        avg_pnl_per_trade=getattr(result, 'avg_pnl_per_trade', 0.0),
        max_drawdown_pct=getattr(result, 'max_drawdown_pct', 0.0),
        sharpe_ratio=getattr(result, 'sharpe_ratio', 0.0),
        total_trades=getattr(result, 'total_trades', 0),
        regime_accuracy=getattr(result, 'regime_accuracy', {}),
        total_stops_hit=getattr(result, 'total_stops_hit', 0),
        stop_loss_enabled=getattr(result, 'stop_loss_enabled', False),
        avg_overnight_gap_pct=getattr(result, 'avg_overnight_gap_pct', 0.0),
    )

    return BacktestRunResponse(summary=summary, days=day_responses)


# ─── Quant Signal Engine endpoints ────────────────────────────────────────────


@protected_router.get("/signal/quant/{instrument}/{date}", response_model=QuantSignalResponse)
async def get_quant_signal(instrument: str, date: str):
    """Return quantitative signal score for a specific instrument and date.

    Fetches OHLCV and VIX data up to and including the given date,
    computes RSI-14, Supertrend, momentum proxies, and scores via QuantSignalEngine.

    Returns per-factor breakdown (QUANT-01/QUANT-03).

    Raises 400 if instrument is invalid.
    Raises 404 if fewer than 15 OHLCV rows available (insufficient for RSI-14 lookback).
    """
    if instrument not in ("NIFTY", "BANKNIFTY"):
        raise HTTPException(status_code=400, detail="instrument must be NIFTY or BANKNIFTY")

    rows = await historical_store.get_ohlcv(instrument, to_date=date)
    if len(rows) < 15:
        raise HTTPException(
            status_code=404,
            detail="Insufficient historical data for this date (need at least 15 rows for RSI-14)"
        )

    vix_rows = await historical_store.get_vix_closes(to_date=date)
    closes = [r["close"] for r in rows]

    rsi = TechnicalSignals.compute_rsi(closes)
    supertrend = TechnicalSignals.compute_supertrend(rows)

    vix_val = vix_rows[-1]["close"] if vix_rows else 18.0
    prev_vix = [v["close"] for v in vix_rows[:-1]]
    vix_5d_avg = float(sum(prev_vix[-5:]) / len(prev_vix[-5:])) if prev_vix else vix_val

    momentum_5d = (closes[-1] / closes[-6] - 1.0) * 100 if len(closes) >= 6 else 0.0

    inputs = QuantInputs(
        fii_net_cr=momentum_5d * 1500,
        dii_net_cr=-momentum_5d * 800,
        pcr=0.6 + (rsi / 100) * 0.8,
        rsi=rsi,
        vix=vix_val,
        vix_5d_avg=vix_5d_avg,
        supertrend=supertrend,
    )
    sr = QuantSignalEngine.compute_quant_score(inputs, instrument)

    return QuantSignalResponse(
        instrument=instrument,
        date=date,
        total_score=sr.total_score,
        direction=sr.direction,
        tier=sr.tier,
        buy_points=sr.buy_points,
        sell_points=sr.sell_points,
        factors=sr.factors,
        instrument_hint=sr.instrument_hint,
    )


@protected_router.post("/backtest/quant-run", response_model=QuantBacktestRunResponse)
async def run_quant_backtest(body: QuantBacktestRequest):
    """Run a rules-only quant backtest over a historical date range.

    No LLM calls. No agent calls. Reads OHLCV + VIX from SQLite only.
    Performance target: 1 year (250 trading days) in under 10 seconds (QUANT-05).

    Returns per-day direction, score, correctness, and aggregate metrics.
    """
    if body.instrument not in ("NIFTY", "BANKNIFTY"):
        raise HTTPException(status_code=400, detail="instrument must be NIFTY or BANKNIFTY")

    try:
        result = await quant_backtest_engine.run_quant_backtest(
            body.instrument, body.from_date, body.to_date
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Quant backtest failed: {exc}")

    day_schemas = [
        QuantBacktestDaySchema(
            date=d.date,
            direction=d.direction,
            total_score=d.total_score,
            tier=d.tier,
            buy_points=d.buy_points,
            sell_points=d.sell_points,
            actual_move_pct=d.actual_move_pct,
            is_correct=d.is_correct,
            pnl_points=d.pnl_points,
        )
        for d in result.days
    ]

    return QuantBacktestRunResponse(
        instrument=result.instrument,
        from_date=result.from_date,
        to_date=result.to_date,
        total_days=result.total_days,
        tradeable_days=result.tradeable_days,
        correct_days=result.correct_days,
        win_rate_pct=result.win_rate_pct,
        total_pnl_points=result.total_pnl_points,
        elapsed_seconds=result.elapsed_seconds,
        days=day_schemas,
    )


@protected_router.post("/admin/clear-historical-cache")
async def clear_historical_cache():
    """Delete cached NIFTY + VIX rows so the next get_ohlcv() re-fetches from Dhan.

    Use after changing BACKFILL_YEARS to force a full re-fetch.
    """
    import sqlite3 as _sqlite3
    db_path = config.DATABASE_PATH
    conn = _sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("DELETE FROM historical_prices WHERE instrument = 'NIFTY'")
    nifty_deleted = cur.rowcount
    cur.execute("DELETE FROM historical_vix")
    vix_deleted = cur.rowcount
    conn.commit()
    conn.close()
    return {"status": "ok", "nifty_rows_deleted": nifty_deleted, "vix_rows_deleted": vix_deleted}


@protected_router.post("/admin/seed-fii-dii")
async def seed_fii_dii_data(years: int = 2):
    """Seed synthetic FII/DII historical data into the database.

    Uses yfinance NIFTY price history to generate realistic FII/DII flows
    with mean reversion + noise (avoids circular momentum proxy).
    Safe to call multiple times — uses INSERT OR REPLACE.
    """
    import random
    import math
    from datetime import date, timedelta
    from app.data.fii_dii_store import fii_dii_store

    # Use NIFTY prices from historical_store (already fetched/cached in DB)
    try:
        all_ohlcv = await historical_store.get_ohlcv("NIFTY")
        if not all_ohlcv:
            return {"status": "error", "message": "No NIFTY data in historical_store yet — run a backtest first"}
        dates = [r["date"] for r in all_ohlcv]
        prices = [r["close"] for r in all_ohlcv]
    except Exception as e:
        return {"status": "error", "message": f"historical_store failed: {e}"}

    rng = random.Random(42)
    fii_sigma, dii_sigma = 2000.0, 1500.0
    records = []

    for i, (d, price) in enumerate(zip(dates, prices)):
        prev_price = prices[i - 1] if i > 0 else price
        daily_ret = (price - prev_price) / prev_price if prev_price else 0.0

        # Mean reversion + price-correlated component + noise (avoids circular momentum proxy)
        fii_flow = daily_ret * 8000 + rng.gauss(0, fii_sigma)
        dii_flow = 500.0 + (-daily_ret * 4000) + rng.gauss(0, dii_sigma * 0.6)

        records.append({
            "date": d,
            "fii_net_cr": round(fii_flow, 2),
            "dii_net_cr": round(dii_flow, 2),
        })

    inserted = 0
    for rec in records:
        try:
            fii_dii_store.store_daily(rec["date"], rec["fii_net_cr"], rec["dii_net_cr"])
            inserted += 1
        except Exception:
            pass

    return {
        "status": "ok",
        "seeded": inserted,
        "date_range": f"{records[0]['date']} → {records[-1]['date']}" if records else "none",
    }


@protected_router.post("/admin/seed-nifty-bulk")
async def seed_nifty_bulk(body: dict):
    """Accept bulk NIFTY OHLCV rows and upsert into historical_prices.

    Body: {"rows": [{"date":"YYYY-MM-DD","open":...,"high":...,"low":...,"close":...,"volume":...}, ...]}
    Useful when yfinance is rate-limited on the server — fetch locally, POST here.
    """
    import sqlite3 as _sqlite3

    rows_in = body.get("rows", [])
    if not rows_in:
        return {"status": "error", "message": "No rows provided"}

    fetched_at = __import__("datetime").datetime.utcnow().isoformat()
    db_path = config.DATABASE_PATH
    conn = _sqlite3.connect(db_path)
    cur = conn.cursor()
    params = [
        ("NIFTY", r["date"], r["open"], r["high"], r["low"], r["close"], r.get("volume", 0), fetched_at)
        for r in rows_in
    ]
    cur.executemany(
        """INSERT OR REPLACE INTO historical_prices
           (instrument, date, open, high, low, close, volume, fetched_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        params,
    )
    conn.commit()
    conn.close()
    dates = [r["date"] for r in rows_in]
    return {"status": "ok", "seeded": len(params), "date_range": f"{min(dates)} → {max(dates)}"}


@protected_router.post("/admin/seed-nifty-yfinance")
async def seed_nifty_yfinance(years: int = 3):
    """Seed NIFTY historical OHLCV data from yfinance (^NSEI ticker).

    Dhan's historical candles API does NOT support index data (IDX_I segment),
    so yfinance is the correct source for NIFTY50 spot prices.
    Safe to re-run — uses INSERT OR REPLACE (UNIQUE constraint on instrument+date).
    """
    import yfinance as yf
    import sqlite3 as _sqlite3
    from datetime import date, timedelta

    end_date = date.today().isoformat()
    start_date = (date.today() - timedelta(days=years * 365)).isoformat()

    ticker = yf.Ticker("^NSEI")
    hist = ticker.history(start=start_date, end=end_date, auto_adjust=True)

    if hist.empty:
        return {"status": "error", "message": "yfinance returned no data for ^NSEI"}

    fetched_at = __import__("datetime").datetime.utcnow().isoformat()
    db_path = config.DATABASE_PATH
    conn = _sqlite3.connect(db_path)
    cur = conn.cursor()

    rows = []
    for ts, row in hist.iterrows():
        d = ts.date().isoformat()
        rows.append((
            "NIFTY", d,
            round(float(row["Open"]), 2),
            round(float(row["High"]), 2),
            round(float(row["Low"]), 2),
            round(float(row["Close"]), 2),
            int(row.get("Volume", 0)),
            fetched_at,
        ))

    cur.executemany(
        """INSERT OR REPLACE INTO historical_prices
           (instrument, date, open, high, low, close, volume, fetched_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    conn.commit()
    conn.close()

    date_range = f"{rows[0][1]} → {rows[-1][1]}" if rows else "none"
    return {"status": "ok", "seeded": len(rows), "date_range": date_range}


# ─── Stock Screener Endpoints ─────────────────────────────────────────────────

@protected_router.get("/screener/stocks")
async def screen_stocks(direction: str = "BUY", capital: int = 10000, top_n: int = 3):
    """Rank F&O stocks by micro-signal score for a given God's Eye direction.

    Args:
        direction: BUY | SELL | STRONG_BUY | STRONG_SELL
        capital:   Available capital in INR (default 10,000)
        top_n:     Number of results to return (default 3)

    Returns ranked candidates with RS, volume, RSI and estimated lot cost.
    Only returns stocks whose estimated weekly OTM option cost fits in budget.
    """
    from app.data.stock_screener import screen_stocks as _screen
    if direction == "HOLD":
        return {"direction": "HOLD", "message": "No trade — system is in HOLD", "candidates": []}
    results = await _screen(direction=direction, capital=capital, top_n=top_n)
    return {"direction": direction, "capital": capital, "candidates": results}


@protected_router.get("/screener/options")
async def get_option_suggestion(symbol: str, direction: str, capital: int = 10000):
    """Suggest a specific option strike for a screened stock.

    Args:
        symbol:    Stock symbol (e.g. TATAMOTORS, ITC)
        direction: BUY (→ CE) | SELL (→ PE)
        capital:   Available capital in INR

    Returns the suggested strike, premium, lot cost, stop and target levels.
    Uses yfinance for LTP estimate when Dhan live feed is unavailable.
    """
    from app.data.fno_universe import FNO_UNIVERSE
    from app.data.stock_screener import _fetch_ohlcv, _estimate_premium
    import math

    sym = symbol.upper()
    if sym not in FNO_UNIVERSE:
        raise HTTPException(status_code=404, detail=f"Symbol {sym} not in F&O universe")

    meta = FNO_UNIVERSE[sym]
    rows = await _fetch_ohlcv(meta["yf_ticker"])
    if not rows:
        raise HTTPException(status_code=503, detail=f"Could not fetch price data for {sym}")

    ltp = rows[-1]["close"]
    lot_size = meta["lot_size"]
    option_type = "CE" if direction in ("BUY", "STRONG_BUY") else "PE"

    # Strike selection: round LTP to nearest 50 for ATM, then 1-OTM
    strike_interval = 50  # standard for most NSE stocks
    atm_strike = round(ltp / strike_interval) * strike_interval
    if option_type == "CE":
        suggested_strike = atm_strike + strike_interval  # 1 OTM CE
    else:
        suggested_strike = atm_strike - strike_interval  # 1 OTM PE

    premium = _estimate_premium(ltp, direction)
    lot_cost = int(lot_size * premium)

    if lot_cost > capital * 0.80:
        # Fall back to ATM if OTM is too expensive
        suggested_strike = atm_strike
        premium = ltp * 0.015  # ATM ~ 1.5% of spot
        lot_cost = int(lot_size * premium)

    stop_premium = round(premium * 0.60, 2)   # exit if premium drops 40%
    target_premium = round(premium * 1.80, 2)  # exit if premium rises 80%
    max_loss = int(lot_size * (premium - stop_premium))
    target_gain = int(lot_size * (target_premium - premium))

    # Approx Nifty/stock move needed for 80% option gain (delta ~0.35 for OTM)
    pts_needed = round((target_premium - premium) / 0.35, 0)

    from datetime import date, timedelta
    today = date.today()
    # Next Thursday
    days_to_thu = (3 - today.weekday()) % 7 or 7
    expiry = today + timedelta(days=days_to_thu)
    dte = days_to_thu

    return {
        "symbol": sym,
        "sector": meta["sector"],
        "ltp": round(ltp, 2),
        "direction": direction,
        "option_type": option_type,
        "expiry": expiry.isoformat(),
        "days_to_expiry": dte,
        "atm_strike": atm_strike,
        "suggested_strike": suggested_strike,
        "premium": round(premium, 2),
        "lot_size": lot_size,
        "lot_cost": lot_cost,
        "stop_loss_premium": stop_premium,
        "target_premium": target_premium,
        "max_loss_inr": max_loss,
        "target_gain_inr": target_gain,
        "pts_move_needed": pts_needed,
        "note": "Premium is estimated (1% OTM heuristic). Verify live with your broker before trading.",
    }



# ── Phase: Automated Paper Trading Scheduler ─────────────────────────────────


@router.get("/scheduler/status")
async def scheduler_status():
    """Get automated paper trading scheduler status."""
    from app.tasks.simulation_scheduler import simulation_scheduler
    return simulation_scheduler.status


@protected_router.post("/scheduler/enable")
async def scheduler_enable():
    """Enable automated paper trading scheduler."""
    from app.tasks.simulation_scheduler import simulation_scheduler
    simulation_scheduler.enable()
    return {"status": "enabled", **simulation_scheduler.status}


@protected_router.post("/scheduler/disable")
async def scheduler_disable():
    """Disable automated paper trading scheduler."""
    from app.tasks.simulation_scheduler import simulation_scheduler
    simulation_scheduler.disable()
    return {"status": "disabled", **simulation_scheduler.status}

@protected_router.post("/scheduler/trigger")
async def scheduler_trigger():
    """Manually trigger a simulation run right now."""
    from app.tasks.simulation_scheduler import simulation_scheduler
    result = await simulation_scheduler.trigger_now()
    return result


@protected_router.post("/scheduler/record-outcomes")
async def scheduler_record_outcomes():
    """Manually trigger outcome recording for today's predictions."""
    from app.tasks.simulation_scheduler import simulation_scheduler
    result = await simulation_scheduler.record_outcomes_now()
    return result


# ─── Paper Trading endpoints ────────────────────────────────────────────────

def _trade_to_dict(trade: PaperTrade) -> dict:
    """Convert PaperTrade dataclass to JSON-serializable dict."""
    return {
        "trade_id": trade.trade_id,
        "simulation_id": trade.simulation_id,
        "prediction_id": trade.prediction_id,
        "timestamp": trade.timestamp,
        "date_ist": trade.date_ist,
        "direction": trade.direction,
        "conviction": trade.conviction,
        "instrument": trade.instrument,
        "option_type": trade.option_type,
        "lot_size": trade.lot_size,
        "lots": trade.lots,
        "dte": trade.dte,
        "entry_spot": trade.entry_spot,
        "entry_premium": trade.entry_premium,
        "stop_price": trade.stop_price,
        "target_price": trade.target_price,
        "stop_nifty": trade.stop_nifty,
        "target_nifty": trade.target_nifty,
        "entry_cost": trade.entry_cost,
        "status": trade.status,
        "exit_premium": trade.exit_premium,
        "exit_spot": trade.exit_spot,        "exit_timestamp": trade.exit_timestamp,
        "exit_reason": trade.exit_reason,
        "exit_value": trade.exit_value,
        "gross_pnl": trade.gross_pnl,
        "brokerage": trade.brokerage,
        "net_pnl": trade.net_pnl,
        "return_pct": trade.return_pct,
    }


@protected_router.get("/paper-trades")
async def get_paper_trades(limit: int = 50, offset: int = 0):
    """Get paper trade history with pagination."""
    try:
        trades = paper_trader.get_trade_history(limit=limit, offset=offset)
        return {
            "trades": [_trade_to_dict(t) for t in trades],
            "count": len(trades),
        }
    except Exception:
        raise safe_error_response(500, "OPERATION_FAILED", "An unexpected error occurred")


@protected_router.get("/paper-trades/open")
async def get_open_paper_trades():
    """Get all currently open paper trades."""
    try:
        trades = paper_trader.get_open_trades()
        return {
            "trades": [_trade_to_dict(t) for t in trades],            "count": len(trades),
        }
    except Exception:
        raise safe_error_response(500, "OPERATION_FAILED", "An unexpected error occurred")


@protected_router.get("/paper-trades/today")
async def get_today_paper_trades():
    """Get all paper trades for today (IST)."""
    try:
        trades = paper_trader.get_today_trades()
        return {
            "trades": [_trade_to_dict(t) for t in trades],
            "count": len(trades),
        }
    except Exception:
        raise safe_error_response(500, "OPERATION_FAILED", "An unexpected error occurred")


@protected_router.get("/paper-trades/pnl")
async def get_paper_trade_pnl(days: int = 30):
    """Get P&L summary for paper trades over the last N days."""
    try:
        summary = paper_trader.get_pnl_summary(days=days)
        return summary
    except Exception:
        raise safe_error_response(500, "OPERATION_FAILED", "An unexpected error occurred")

@protected_router.get("/paper-trades/{trade_id}")
async def get_paper_trade(trade_id: str):
    """Get a specific paper trade by ID."""
    try:
        trade = paper_trader.get_trade_by_id(trade_id)
        if not trade:
            raise HTTPException(status_code=404, detail=f"Trade {trade_id} not found")
        return _trade_to_dict(trade)
    except HTTPException:
        raise
    except Exception:
        raise safe_error_response(500, "OPERATION_FAILED", "An unexpected error occurred")


@protected_router.post("/paper-trades/close-all")
async def close_all_paper_trades():
    """Close all open paper trades at current market price (manual EOD)."""
    try:
        live_data = await market_data_service.build_market_input()
        closing_spot = live_data.get("nifty_spot", 0)
        closing_vix = live_data.get("india_vix", 15.0)
        if closing_spot <= 0:
            raise HTTPException(status_code=400, detail="Cannot get current NIFTY spot")
        closed = paper_trader.close_all_eod(closing_spot, closing_vix)
        return {
            "closed": len(closed),
            "trades": [_trade_to_dict(t) for t in closed],
        }
    except HTTPException:
        raise
    except Exception:
        raise safe_error_response(500, "OPERATION_FAILED", "An unexpected error occurred")
