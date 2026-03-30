"""FastAPI routes for God's Eye."""

import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from app.auth.middleware import require_auth
from app.limiter import limiter
from app.api.schemas import (
    MarketInput,
    SimulationResult,
    PresetScenario,
    AggregatorResult,
)
from app.api.errors import safe_error_response, log_error_safely
from app.engine.orchestrator import Orchestrator
from app.engine.aggregator import Aggregator
from app.engine.scenarios import ScenarioGenerator
from app.engine.feedback_engine import FeedbackEngine
from app.memory.prediction_tracker import PredictionTracker
from app.memory.agent_memory import AgentMemory
from app.data.market_data import market_data_service
from app.data.cache import cache
from app.config import config

# Public router for health checks and auth endpoints
router = APIRouter(prefix="/api", tags=["health", "auth"])

# Protected router for all other endpoints
protected_router = APIRouter(prefix="/api", tags=["simulation"], dependencies=[Depends(require_auth)])

# Initialize components
tracker = PredictionTracker()


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

        return response

    except HTTPException:
        raise
    except Exception as e:
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
    except Exception as e:
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
    except Exception as e:
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
    except Exception as e:
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
    except Exception as e:
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
    except Exception as e:
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
    except Exception as e:
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
    except Exception as e:
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
    except Exception as e:
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
    except Exception as e:
        raise safe_error_response(500, "OPERATION_FAILED", "An unexpected error occurred")


@protected_router.get("/market/options")
async def get_options_data(symbol: str = "NIFTY"):
    """Get options chain summary: PCR, max pain, top OI strikes."""
    try:
        data = await market_data_service.get_options_chain(symbol)
        return data
    except Exception as e:
        raise safe_error_response(500, "OPERATION_FAILED", "An unexpected error occurred")


@protected_router.get("/market/sectors")
async def get_sectors():
    """Get sector index values with % change."""
    try:
        sectors = await market_data_service.get_sector_indices()
        return {"sectors": sectors}
    except Exception as e:
        raise safe_error_response(500, "OPERATION_FAILED", "An unexpected error occurred")


@protected_router.get("/market/cache-stats")
async def get_cache_stats():
    """Get cache statistics for debugging."""
    return cache.stats()


@router.get("/health")
async def health_check():
    """Health check endpoint with database connectivity check."""
    import os
    import sqlite3
    from datetime import datetime as dt
    import time

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
        from app.auth.device_auth import DeviceAuthManager
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
    except Exception as e:
        raise safe_error_response(500, "LOGIN_FAILED", "Login initiation failed. Please try again.")


@router.post("/auth/poll")
@limiter.limit("30/minute")
async def poll_auth(request: Request, device_code: str, provider: str = "openai"):
    """Poll for device code authorization. Call this repeatedly until authorized.

    Returns status: "waiting" | "authorized" | "expired" | "error"
    """
    try:
        from app.auth.device_auth import DeviceAuthManager, DeviceCodeResponse
        auth = DeviceAuthManager(provider=provider)

        # Single poll attempt (non-blocking)
        import httpx
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
            import time
            from app.auth.device_auth import AuthTokens
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

    except Exception as e:
        raise safe_error_response(500, "OPERATION_FAILED", "An unexpected error occurred")


@router.get("/auth/status")
async def get_auth_status():
    """Check current authentication status."""
    try:
        from app.auth.device_auth import get_auth_manager
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
        from app.auth.device_auth import get_auth_manager
        auth = get_auth_manager()
        auth.logout()
        config.MOCK_MODE = True
        return {"status": "logged_out"}
    except Exception as e:
        raise safe_error_response(500, "OPERATION_FAILED", "An unexpected error occurred")


# ─── Learning / Skills endpoints ──────────────────────────────────────────

@protected_router.get("/learning/skills")
async def list_skills():
    """List all learned skills across agents."""
    try:
        from app.learning.skill_store import get_skill_store
        store = get_skill_store()
        skills = store.list_skills_summary()
        return {
            "total_skills": len(skills),
            "learning_enabled": config.LEARNING_ENABLED,
            "skills": skills,
        }
    except Exception as e:
        raise safe_error_response(500, "OPERATION_FAILED", "An unexpected error occurred")


@protected_router.get("/learning/skills/{agent_id}")
async def get_agent_skills(agent_id: str):
    """List learned skills for a specific agent."""
    try:
        from app.learning.skill_store import get_skill_store
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
    except Exception as e:
        raise safe_error_response(500, "OPERATION_FAILED", "An unexpected error occurred")


@protected_router.post("/learning/toggle")
async def toggle_learning(enabled: bool = True):
    """Enable or disable the auto-learning system."""
    config.LEARNING_ENABLED = enabled
    return {
        "learning_enabled": config.LEARNING_ENABLED,
        "skill_directory": config.LEARNING_SKILL_DIR,
    }
