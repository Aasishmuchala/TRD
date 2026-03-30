"""SQLAlchemy ORM models for God's Eye database schema.

Maps to the current raw SQLite schema in prediction_tracker.py and agent_memory.py.
Used with Alembic for schema migrations and versioning.
"""

from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, JSON, DateTime, Text, create_engine
from sqlalchemy.orm import declarative_base

# Base class for all models
Base = declarative_base()


class Simulation(Base):
    """Simulation run record.

    Corresponds to the simulations table in prediction_tracker.py.
    """
    __tablename__ = "simulations"

    simulation_id = Column(String, primary_key=True)
    timestamp = Column(String, nullable=False)  # ISO format datetime
    market_input = Column(JSON, nullable=False)  # Market input parameters as JSON
    agents_output = Column(JSON, nullable=False)  # Agent predictions as JSON
    final_direction = Column(String, nullable=False)  # STRONG_BUY, BUY, HOLD, SELL, STRONG_SELL
    final_conviction = Column(Float, nullable=False)  # 0-100
    execution_time_ms = Column(Float, nullable=False)  # Execution time in milliseconds
    model_used = Column(String, nullable=False)  # e.g., "o4-mini", "gpt-4", etc.


class Prediction(Base):
    """Individual prediction record for accuracy tracking.

    Corresponds to the predictions table in prediction_tracker.py.
    """
    __tablename__ = "predictions"

    prediction_id = Column(String, primary_key=True)
    simulation_id = Column(String, nullable=False)
    timestamp = Column(String, nullable=False)  # ISO format datetime
    market_input = Column(JSON, nullable=False)  # Market input as JSON
    predicted_direction = Column(String, nullable=False)  # STRONG_BUY, BUY, HOLD, SELL, STRONG_SELL
    predicted_conviction = Column(Float, nullable=False)  # 0-100
    agents_output = Column(JSON, nullable=False)  # Agent outputs as JSON
    actual_direction = Column(String)  # Set after outcome is known
    check_timestamp = Column(String)  # ISO format datetime when outcome was recorded
    accuracy = Column(Integer)  # 1 if correct, 0 if wrong, NULL if not yet evaluated
    notes = Column(Text)  # Optional notes on the outcome


class AgentMemory(Base):
    """Per-agent prediction memory with accuracy tracking.

    Corresponds to agent_predictions table in agent_memory.py.
    Tracks individual agent predictions within a simulation.
    """
    __tablename__ = "agent_predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    simulation_id = Column(String, nullable=False)
    agent_key = Column(String, nullable=False)  # FII, DII, RETAIL_FNO, ALGO, PROMOTER, RBI
    timestamp = Column(String, nullable=False)  # ISO format datetime
    context = Column(String, default="normal")  # normal, weekly_expiry, monthly_expiry
    direction = Column(String, nullable=False)  # STRONG_BUY, BUY, HOLD, SELL, STRONG_SELL
    conviction = Column(Float, nullable=False)  # 0-100
    reasoning = Column(Text)  # Agent's reasoning text
    key_triggers = Column(JSON)  # List of key triggers that influenced the prediction
    round_num = Column(Integer, default=3)  # Interaction round number
    actual_direction = Column(String)  # Set after outcome is known
    was_correct = Column(Integer)  # 1 if correct, 0 if wrong, NULL if not yet evaluated
    market_snapshot = Column(JSON)  # Market data snapshot at prediction time


class AgentWeightHistory(Base):
    """Agent weight adjustment history.

    Corresponds to agent_weight_history table in agent_memory.py.
    Tracks how agent weights change over time based on accuracy.
    """
    __tablename__ = "agent_weight_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(String, nullable=False)  # ISO format datetime
    agent_key = Column(String, nullable=False)  # Agent identifier
    old_weight = Column(Float, nullable=False)  # Previous weight
    new_weight = Column(Float, nullable=False)  # New weight
    reason = Column(Text)  # Reason for adjustment
