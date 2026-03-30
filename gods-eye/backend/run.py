"""FastAPI application entry point."""

import json
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.limiter import limiter
from app.api.routes import router, protected_router
from app.api.schemas import MarketInput
from app.engine.streaming_orchestrator import StreamingOrchestrator
from app.engine.scenarios import ScenarioGenerator
from app.data.market_data import market_data_service
from app.config import config

# Define rate limit exceeded handler first
async def _rate_limit_exceeded_handler(request, exc):
    """Handle rate limit exceeded errors."""
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."},
    )


# Create FastAPI app
app = FastAPI(
    title="God's Eye",
    description="Multi-Agent AI Market Simulation for Indian Markets",
    version="2.0.0",
)

# Store limiter in app state for SlowAPI middleware
app.state.limiter = limiter

app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add SlowAPI middleware
app.add_middleware(SlowAPIMiddleware)

# Add CORS middleware to allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Include routes
app.include_router(router)
app.include_router(protected_router)


# ─── WebSocket endpoint (mounted directly on app to avoid CORS issues) ───
@app.websocket("/api/simulate/stream")
async def websocket_simulate_stream(websocket: WebSocket):
    """Stream simulation events over WebSocket.

    Client sends JSON to start:
        {"scenario_id": "rbi_rate_cut"}  or
        {"source": "live"}              or
        {"market_input": {...}}
    """
    await websocket.accept()
    try:
        data = await websocket.receive_json()
        market_input = None
        data_source = "fallback"

        if data.get("source") == "live":
            live_data = await market_data_service.build_market_input()
            mi_fields = {k: v for k, v in live_data.items() if not k.startswith("_")}
            market_input = MarketInput(**mi_fields)
            live_extras = {k: v for k, v in live_data.items() if k.startswith("_")}
            snapshot = await market_data_service.get_live_snapshot()
            data_source = snapshot.get("data_source", "nse_live")
            await websocket.send_json({"type": "live_data", "data": live_extras})

        elif data.get("scenario_id"):
            scenarios = ScenarioGenerator.get_all_scenarios()
            for scenario in scenarios:
                if scenario.scenario_id == data["scenario_id"]:
                    market_input = scenario.market_data
                    break
            if not market_input:
                await websocket.send_json({"type": "error", "message": f"Scenario not found"})
                await websocket.close()
                return

        elif data.get("market_input"):
            market_input = MarketInput(**data["market_input"])

        elif data.get("nifty_spot") is not None:
            market_input = MarketInput(
                nifty_spot=data["nifty_spot"],
                india_vix=data.get("india_vix", 15.0),
                fii_flow_5d=data.get("fii_flow_5d", 0.0),
                dii_flow_5d=data.get("dii_flow_5d", 0.0),
                usd_inr=data.get("usd_inr", 83.0),
                dxy=data.get("dxy", 104.0),
                pcr_index=data.get("pcr_index", 1.0),
                max_pain=data.get("max_pain", data["nifty_spot"]),
                dte=data.get("dte", 5),
                context=data.get("context", "normal"),
            )

        if not market_input:
            await websocket.send_json({"type": "error", "message": "Invalid request"})
            await websocket.close()
            return

        orchestrator = StreamingOrchestrator()
        async for event in orchestrator.stream_simulation(market_input, data_source=data_source):
            await websocket.send_json(event)

        await websocket.close()

    except WebSocketDisconnect:
        pass
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
            await websocket.close()
        except Exception:
            pass


@app.on_event("startup")
async def startup_event():
    """Startup event handler."""
    from app.logging_config import setup_logging
    setup_logging()
    print(f"Starting God's Eye with model: {config.MODEL}")


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler."""
    print("Shutting down God's Eye")
    # Close market data service resources
    await market_data_service.shutdown()
    # Close LLM client if available
    from app.auth.llm_client import get_llm_client
    llm_client = get_llm_client()
    await llm_client.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "run:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.RELOAD,
        log_level="info",
    )
