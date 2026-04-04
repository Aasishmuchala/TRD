"""Tests for the SkillStore and Skill system."""

import os
import tempfile
import pytest
from pathlib import Path
from datetime import datetime

from app.learning.skill_store import Skill, SkillStore


@pytest.fixture
def temp_skill_dir():
    """Provide a temporary directory for skill files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


def test_create_and_save_skill(temp_skill_dir):
    """Test creating a skill and saving it to disk."""
    store = SkillStore(base_dir=temp_skill_dir)

    skill = Skill(
        name="High VIX Caution",
        agent="FII",
        description="Lower conviction when VIX > 22",
        content="When India VIX exceeds 22, FII flows historically reverse.",
        trigger_conditions=["india_vix > 22"],
        success_rate=0.73,
        times_applied=15,
    )

    filepath = store.save_skill(skill)

    # Verify file was created
    assert os.path.exists(filepath)
    assert "high_vix_caution.md" in filepath
    assert "FII" in filepath

    # Verify content
    content = Path(filepath).read_text()
    assert "---" in content
    assert "High VIX Caution" in content
    assert "india_vix > 22" in content


def test_load_skills_back(temp_skill_dir):
    """Test loading a skill back from disk."""
    store = SkillStore(base_dir=temp_skill_dir)

    # Save a skill
    skill = Skill(
        name="High VIX Caution",
        agent="FII",
        description="Lower conviction when VIX > 22",
        content="When India VIX exceeds 22, FII flows historically reverse.",
        trigger_conditions=["india_vix > 22"],
        success_rate=0.73,
        times_applied=15,
    )
    store.save_skill(skill)

    # Load it back
    loaded_skills = store.load_skills("FII")

    assert len(loaded_skills) == 1
    loaded = loaded_skills[0]
    assert loaded.name == "High VIX Caution"
    assert loaded.agent == "FII"
    assert loaded.description == "Lower conviction when VIX > 22"
    assert loaded.success_rate == 0.73
    assert loaded.times_applied == 15


def test_matches_context_single_condition_true(temp_skill_dir):
    """Test matches_context with condition that matches."""
    skill = Skill(
        name="High VIX Caution",
        agent="FII",
        description="Test",
        content="Test",
        trigger_conditions=["india_vix > 22"],
    )

    market_data = {
        "india_vix": 25.0,
        "nifty_spot": 24000.0,
    }

    assert skill.matches_context(market_data) is True


def test_matches_context_single_condition_false(temp_skill_dir):
    """Test matches_context with condition that does not match."""
    skill = Skill(
        name="High VIX Caution",
        agent="FII",
        description="Test",
        content="Test",
        trigger_conditions=["india_vix > 22"],
    )

    market_data = {
        "india_vix": 15.0,
        "nifty_spot": 24000.0,
    }

    assert skill.matches_context(market_data) is False


def test_matches_context_multiple_conditions_and_logic(temp_skill_dir):
    """Test matches_context with multiple conditions (AND logic)."""
    skill = Skill(
        name="Complex Pattern",
        agent="DII",
        description="Test",
        content="Test",
        trigger_conditions=[
            "india_vix > 20",
            "fii_flow_5d < 0",
            "nifty_spot > 23000",
        ],
    )

    # All conditions met
    market_data = {
        "india_vix": 25.0,
        "fii_flow_5d": -100.0,
        "nifty_spot": 24000.0,
    }
    assert skill.matches_context(market_data) is True

    # One condition not met
    market_data = {
        "india_vix": 15.0,  # Not > 20
        "fii_flow_5d": -100.0,
        "nifty_spot": 24000.0,
    }
    assert skill.matches_context(market_data) is False

    # Another condition not met
    market_data = {
        "india_vix": 25.0,
        "fii_flow_5d": 100.0,  # Not < 0
        "nifty_spot": 24000.0,
    }
    assert skill.matches_context(market_data) is False


def test_malformed_yaml_skipped_gracefully(temp_skill_dir):
    """Test that malformed YAML skill files are skipped gracefully."""
    store = SkillStore(base_dir=temp_skill_dir)

    # Create FII directory and add malformed file
    fii_dir = Path(temp_skill_dir) / "FII"
    fii_dir.mkdir()

    malformed_file = fii_dir / "bad_skill.md"
    malformed_file.write_text("""---
name: Bad Skill
agent: FII
trigger_conditions: [invalid yaml: [
---
Content here
""")

    # Load should skip the malformed file
    loaded_skills = store.load_skills("FII")
    assert len(loaded_skills) == 0  # Malformed file is skipped


def test_build_skill_context_no_matching_skills(temp_skill_dir):
    """Test build_skill_context returns empty string when no skills match."""
    store = SkillStore(base_dir=temp_skill_dir)

    skill = Skill(
        name="High VIX Only",
        agent="FII",
        description="Test",
        content="Test content",
        trigger_conditions=["india_vix > 22"],
    )
    store.save_skill(skill)

    market_data = {
        "india_vix": 15.0,  # Does not meet > 22
        "nifty_spot": 24000.0,
    }

    context = store.build_skill_context("FII", market_data)
    assert context == ""


def test_build_skill_context_with_matching_skills(temp_skill_dir):
    """Test build_skill_context returns applicable skills as text."""
    store = SkillStore(base_dir=temp_skill_dir)

    skill = Skill(
        name="High VIX Caution",
        agent="FII",
        description="FII behavior under volatility",
        content="When VIX exceeds 22, FII flows reverse.",
        trigger_conditions=["india_vix > 22"],
        success_rate=0.73,
        times_applied=15,
    )
    store.save_skill(skill)

    market_data = {
        "india_vix": 25.0,  # Meets > 22
        "nifty_spot": 24000.0,
    }

    context = store.build_skill_context("FII", market_data)

    # Should contain skill information
    assert "LEARNED PATTERNS" in context
    assert "High VIX Caution" in context
    assert "(success rate: 73%)" in context


def test_list_skills_summary(temp_skill_dir):
    """Test list_skills_summary returns correct summary format."""
    store = SkillStore(base_dir=temp_skill_dir)

    skill1 = Skill(
        name="Skill One",
        agent="FII",
        description="First skill",
        content="Content 1",
        trigger_conditions=["india_vix > 20"],
        success_rate=0.8,
        times_applied=10,
    )

    skill2 = Skill(
        name="Skill Two",
        agent="DII",
        description="Second skill",
        content="Content 2",
        trigger_conditions=["fii_flow_5d < 0"],
        success_rate=0.6,
        times_applied=5,
    )

    store.save_skill(skill1)
    store.save_skill(skill2)

    summary = store.list_skills_summary()

    assert len(summary) == 2

    # Check both skills are present (don't rely on order)
    skill_names = {s["name"] for s in summary}
    assert "Skill One" in skill_names
    assert "Skill Two" in skill_names

    # Check attributes by skill name
    skill_one = next(s for s in summary if s["name"] == "Skill One")
    assert skill_one["agent"] == "FII"
    assert skill_one["success_rate"] == 0.8

    skill_two = next(s for s in summary if s["name"] == "Skill Two")
    assert skill_two["agent"] == "DII"
    assert skill_two["success_rate"] == 0.6
