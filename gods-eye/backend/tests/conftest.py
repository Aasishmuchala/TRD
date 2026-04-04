"""Pytest configuration and shared fixtures for God's Eye tests."""

import os
import tempfile
import pytest
import pytest_asyncio
import httpx
from pathlib import Path
from contextlib import asynccontextmanager

from run import app
from app.config import config


@pytest_asyncio.fixture
async def mock_config():
    """Configure app for testing in mock mode."""
    # Set mock mode to bypass auth
    original_mock = config.MOCK_MODE
    original_db = config.DATABASE_PATH

    # Use temporary database for tests
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        config.DATABASE_PATH = tmp.name
        db_path = tmp.name

    config.MOCK_MODE = True

    yield config

    # Cleanup
    config.MOCK_MODE = original_mock
    config.DATABASE_PATH = original_db
    if os.path.exists(db_path):
        try:
            os.unlink(db_path)
        except:
            pass


@pytest_asyncio.fixture
async def test_client(mock_config):
    """Create an async test client for the FastAPI app without running startup/shutdown events."""
    # Create client without triggering startup/shutdown (those are called per-app, not per-client)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def temp_database():
    """Provide a temporary database path for test isolation."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    yield db_path
    # Cleanup
    if os.path.exists(db_path):
        try:
            os.unlink(db_path)
        except:
            pass
