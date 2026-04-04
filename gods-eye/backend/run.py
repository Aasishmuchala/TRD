"""FastAPI application entry point."""

import json
import os

# Load .env before anything reads os.getenv()
from dotenv import load_dotenv
load_dotenv()

from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import StreamingResponse
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


# ─── SSE endpoint — works through any HTTP proxy/tunnel ───
@app.post("/api/simulate/stream-sse")
async def sse_simulate_stream(request: Request):
    """Stream simulation events via Server-Sent Events (SSE).

    Unlike WebSocket, SSE works through HTTP proxies and tunnel services.
    Client POSTs the simulation request body, receives SSE event stream back.
    """
    body = await request.json()

    async def event_generator():
        try:
            market_input = None
            data_source = "fallback"

            if body.get("source") == "live":
                live_data = await market_data_service.build_market_input()
                mi_fields = {k: v for k, v in live_data.items() if not k.startswith("_")}
                market_input = MarketInput(**mi_fields)
                live_extras = {k: v for k, v in live_data.items() if k.startswith("_")}
                snapshot = await market_data_service.get_live_snapshot()
                data_source = snapshot.get("data_source", "nse_live")
                yield f"data: {json.dumps({'type': 'live_data', 'data': live_extras})}\n\n"

            elif body.get("scenario_id"):
                scenarios = ScenarioGenerator.get_all_scenarios()
                for scenario in scenarios:
                    if scenario.scenario_id == body["scenario_id"]:
                        market_input = scenario.market_data
                        break
                if not market_input:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Scenario not found'})}\n\n"
                    return

            elif body.get("market_input"):
                market_input = MarketInput(**body["market_input"])

            elif body.get("nifty_spot") is not None:
                market_input = MarketInput(
                    nifty_spot=body["nifty_spot"],
                    india_vix=body.get("india_vix", 15.0),
                    fii_flow_5d=body.get("fii_flow_5d", 0.0),
                    dii_flow_5d=body.get("dii_flow_5d", 0.0),
                    usd_inr=body.get("usd_inr", 83.0),
                    dxy=body.get("dxy", 104.0),
                    pcr_index=body.get("pcr_index", 1.0),
                    max_pain=body.get("max_pain", body["nifty_spot"]),
                    dte=body.get("dte", 5),
                    context=body.get("context", "normal"),
                )

            if not market_input:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Invalid request'})}\n\n"
                return

            orchestrator = StreamingOrchestrator()
            async for event in orchestrator.stream_simulation(market_input, data_source=data_source):
                yield f"data: {json.dumps(event)}\n\n"

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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

    # Validate CORS config for production deployments
    _cors = config.CORS_ORIGINS
    _is_localhost_only = all("localhost" in o or "127.0.0.1" in o for o in _cors)
    _env = os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("GODS_EYE_ENV", "development")
    if _is_localhost_only and _env not in ("development", "local", "test"):
        print(
            "WARNING: CORS_ORIGINS only contains localhost origins in a non-development "
            "environment. Set GODS_EYE_CORS_ORIGINS=https://your-app.vercel.app on Railway "
            "or all frontend API calls will be blocked by CORS policy."
        )

    # Validate database path for production deployments
    _db_path = config.DATABASE_PATH
    if _env not in ("development", "local", "test"):
        if not _db_path.startswith("/app/data"):
            print(
                f"WARNING: DATABASE_PATH={_db_path!r} is not under /app/data. "
                "On Railway, this path is ephemeral and will be wiped on redeploy. "
                "Set GODS_EYE_DB_PATH=/app/data/gods_eye.db and mount a Railway Volume at /app/data."
            )
    else:
        print(f"Database path: {_db_path}")

    # Auto-generate/renew Dhan API token if TOTP is configured
    from app.auth.dhan_token_manager import dhan_token_manager
    if dhan_token_manager.is_totp_configured:
        print("Dhan TOTP configured — generating fresh access token...")
        success = await dhan_token_manager.ensure_valid_token()
        if success:
            print(f"Dhan token active (expires: {dhan_token_manager._token_expiry})")
            dhan_token_manager.start_auto_renewal()
        else:
            print("WARNING: Dhan token generation failed — market data may be unavailable")
    elif dhan_token_manager.access_token:
        print("Dhan token found (manual). Starting renewal loop...")
        dhan_token_manager.start_auto_renewal()

    # Start PCR collection background task
    from app.tasks.pcr_collector import pcr_collector
    pcr_collector.start()

    # Start FII/DII collection background task
    from app.tasks.fii_dii_collector import fii_dii_collector
    fii_dii_collector.start()


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler."""
    print("Shutting down God's Eye")
    # Stop PCR collection (uses dhan_client, so stop before token manager)
    from app.tasks.pcr_collector import pcr_collector
    await pcr_collector.shutdown()
    # Stop FII/DII collection
    from app.tasks.fii_dii_collector import fii_dii_collector
    await fii_dii_collector.shutdown()
    # Stop Dhan token renewal
    from app.auth.dhan_token_manager import dhan_token_manager
    await dhan_token_manager.shutdown()
    # Close market data service resources
    await market_data_service.shutdown()
    # Close LLM client if available
    from app.auth.llm_client import get_llm_client
    llm_client = get_llm_client()
    await llm_client.close()


# ─── Serve built frontend (SPA) if dist exists ───
# This allows the entire app to run on a single port (8000),
# which is essential when the browser can't reach the Vite dev server directly.
FRONTEND_DIST = Path(os.getenv("FRONTEND_DIST", "/tmp/gods-eye-dist"))
if FRONTEND_DIST.is_dir() and (FRONTEND_DIST / "index.html").exists():
    # Serve static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="static-assets")

    # SPA catch-all: any non-API route serves index.html
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Don't intercept /api or /docs routes
        if full_path.startswith("api/") or full_path in ("docs", "redoc", "openapi.json"):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        # Serve actual files if they exist (favicon.ico, etc.)
        file_path = FRONTEND_DIST / full_path
        if full_path and file_path.is_file():
            return FileResponse(str(file_path))
        # Otherwise serve index.html for SPA routing
        return FileResponse(str(FRONTEND_DIST / "index.html"))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "run:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.RELOAD,
        log_level="info",
    )
