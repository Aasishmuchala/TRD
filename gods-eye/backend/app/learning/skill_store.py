"""Skill storage and retrieval for auto-learning agents.

Skills are YAML-frontmatter + markdown files stored in ~/.gods-eye/skills/.
Each skill captures a reusable pattern that an agent discovered through
trial and error during simulations.

Adapted from NousResearch/hermes-agent skills system.

Example skill file (skills/fii/high_vix_caution.md):
    ---
    name: High VIX Caution
    agent: FII
    description: FII agent should lower conviction when VIX > 22
    trigger_conditions:
      - india_vix > 22
    created: 2026-03-30T12:00:00
    updated: 2026-03-30T12:00:00
    success_rate: 0.73
    times_applied: 15
    ---

    When India VIX exceeds 22, FII flows historically reverse direction
    within 2-3 sessions. Lower conviction by 15-20% on BUY calls and
    consider HOLD if VIX > 28.

    Evidence: In 15 simulations with VIX > 22, the agent was correct
    73% of the time when applying this caution vs 45% without it.
"""

import os
import json
import yaml
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

from app.config import config

logger = logging.getLogger(__name__)


@dataclass
class Skill:
    """A learned skill that can be injected into agent prompts."""
    name: str
    agent: str  # Agent key (FII, DII, etc.) or "ALL"
    description: str
    content: str  # Markdown body — the actual guidance
    trigger_conditions: List[str]  # When this skill applies
    created: str = ""
    updated: str = ""
    success_rate: float = 0.0
    times_applied: int = 0
    file_path: str = ""

    def matches_context(self, market_data_dict: Dict) -> bool:
        """Check if this skill's trigger conditions match current market data.

        All conditions must be met (AND logic). Unknown fields are skipped.
        """
        if not self.trigger_conditions:
            return True

        for condition in self.trigger_conditions:
            try:
                parts = condition.strip().split()
                if len(parts) != 3:
                    continue  # Skip malformed conditions
                field, op, threshold = parts[0], parts[1], float(parts[2])
                actual = market_data_dict.get(field)
                if actual is None:
                    continue  # Skip unknown fields
                actual = float(actual)

                # Evaluate condition — return False immediately if not met
                OPS = {
                    ">": actual > threshold,
                    "<": actual < threshold,
                    ">=": actual >= threshold,
                    "<=": actual <= threshold,
                    "==": abs(actual - threshold) < 0.001,  # Float-safe equality
                    "!=": abs(actual - threshold) >= 0.001,
                }
                result = OPS.get(op)
                if result is None:
                    continue  # Unknown operator, skip
                if not result:
                    return False  # Condition not met

            except (ValueError, IndexError):
                continue
        return True  # All conditions met


class SkillStore:
    """Manages skill files on disk with YAML frontmatter.

    Skills are organized by agent:
        ~/.gods-eye/skills/
        ├── FII/
        │   ├── high_vix_caution.md
        │   └── dxy_reversal_pattern.md
        ├── DII/
        │   └── sip_flow_momentum.md
        ├── ALL/
        │   └── expiry_week_volatility.md
        └── _index.json  (skill metadata cache)
    """

    def __init__(self, base_dir: str = None):
        self.base_dir = Path(base_dir or config.LEARNING_SKILL_DIR)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Optional[Dict[str, List[Skill]]] = None

    def save_skill(self, skill: Skill) -> str:
        """Save a skill to disk. Returns the file path."""
        # Create agent directory
        agent_dir = self.base_dir / skill.agent
        agent_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename from name
        filename = skill.name.lower().replace(" ", "_").replace("-", "_")
        filename = "".join(c for c in filename if c.isalnum() or c == "_")
        filepath = agent_dir / f"{filename}.md"

        # Build YAML frontmatter
        frontmatter = {
            "name": skill.name,
            "agent": skill.agent,
            "description": skill.description,
            "trigger_conditions": skill.trigger_conditions,
            "created": skill.created or datetime.now().isoformat(),
            "updated": datetime.now().isoformat(),
            "success_rate": skill.success_rate,
            "times_applied": skill.times_applied,
        }

        content = f"---\n{yaml.dump(frontmatter, default_flow_style=False)}---\n\n{skill.content}\n"
        filepath.write_text(content)

        # Invalidate cache
        self._cache = None

        logger.info(f"Saved skill: {skill.name} for agent {skill.agent} -> {filepath}")
        return str(filepath)

    def load_skills(self, agent_key: str = None) -> List[Skill]:
        """Load all skills, optionally filtered by agent."""
        if self._cache is None:
            self._cache = self._scan_all_skills()

        if agent_key:
            # Return skills for this agent + ALL skills
            agent_skills = self._cache.get(agent_key, [])
            all_skills = self._cache.get("ALL", [])
            return agent_skills + all_skills

        # Return everything
        all_skills = []
        for skills in self._cache.values():
            all_skills.extend(skills)
        return all_skills

    def get_applicable_skills(
        self, agent_key: str, market_data_dict: Dict
    ) -> List[Skill]:
        """Get skills that match current market conditions for an agent."""
        skills = self.load_skills(agent_key)
        return [s for s in skills if s.matches_context(market_data_dict)]

    def build_skill_context(
        self, agent_key: str, market_data_dict: Dict
    ) -> str:
        """Build a prompt section from applicable skills for an agent.

        Returns text to inject into the agent's prompt.
        """
        applicable = self.get_applicable_skills(agent_key, market_data_dict)
        if not applicable:
            return ""

        lines = [f"LEARNED PATTERNS ({len(applicable)} applicable):"]
        for skill in applicable[:5]:  # Max 5 to control token usage
            success_str = f" (success rate: {skill.success_rate:.0%})" if skill.times_applied > 0 else ""
            lines.append(f"  [{skill.name}]{success_str}: {skill.content[:200]}")

        return "\n".join(lines)

    def update_skill_outcome(self, skill_name: str, was_successful: bool):
        """Update a skill's success rate after it was applied."""
        skills = self.load_skills()
        for skill in skills:
            if skill.name == skill_name and skill.file_path:
                skill.times_applied += 1
                # Exponential moving average
                alpha = 0.3
                new_outcome = 1.0 if was_successful else 0.0
                if skill.times_applied == 1:
                    skill.success_rate = new_outcome
                else:
                    skill.success_rate = alpha * new_outcome + (1 - alpha) * skill.success_rate
                skill.updated = datetime.now().isoformat()
                self.save_skill(skill)
                break

    def list_skills_summary(self) -> List[Dict]:
        """Get a summary of all skills for the API."""
        skills = self.load_skills()
        return [
            {
                "name": s.name,
                "agent": s.agent,
                "description": s.description,
                "trigger_conditions": s.trigger_conditions,
                "success_rate": s.success_rate,
                "times_applied": s.times_applied,
                "created": s.created,
                "updated": s.updated,
            }
            for s in skills
        ]

    # ─── Internal ─────────────────────────────────────────────────────────

    def _scan_all_skills(self) -> Dict[str, List[Skill]]:
        """Scan disk for all skill files."""
        skills_by_agent: Dict[str, List[Skill]] = {}

        if not self.base_dir.exists():
            return skills_by_agent

        for agent_dir in self.base_dir.iterdir():
            if not agent_dir.is_dir() or agent_dir.name.startswith("_"):
                continue

            agent_key = agent_dir.name
            skills_by_agent[agent_key] = []

            for skill_file in agent_dir.glob("*.md"):
                try:
                    skill = self._parse_skill_file(skill_file, agent_key)
                    if skill:
                        skills_by_agent[agent_key].append(skill)
                except Exception as e:
                    logger.warning(f"Failed to parse skill {skill_file}: {e}")

        return skills_by_agent

    def _parse_skill_file(self, filepath: Path, default_agent: str) -> Optional[Skill]:
        """Parse a YAML-frontmatter skill file."""
        try:
            text = filepath.read_text()
        except (OSError, UnicodeDecodeError) as e:
            logger.warning(f"Cannot read skill file {filepath}: {e}")
            return None

        # Split frontmatter and content
        if not text.startswith("---"):
            return None

        parts = text.split("---", 2)
        if len(parts) < 3:
            return None

        try:
            frontmatter = yaml.safe_load(parts[1])
        except yaml.YAMLError as e:
            logger.warning(f"Malformed YAML in skill file {filepath}: {e}")
            return None

        content = parts[2].strip()

        if not frontmatter or not isinstance(frontmatter, dict):
            return None

        return Skill(
            name=frontmatter.get("name", filepath.stem),
            agent=frontmatter.get("agent", default_agent),
            description=frontmatter.get("description", ""),
            content=content,
            trigger_conditions=frontmatter.get("trigger_conditions", []),
            created=frontmatter.get("created", ""),
            updated=frontmatter.get("updated", ""),
            success_rate=float(frontmatter.get("success_rate", 0.0)),
            times_applied=int(frontmatter.get("times_applied", 0)),
            file_path=str(filepath),
        )


# ─── Global singleton ─────────────────────────────────────────────────────
_skill_store: Optional[SkillStore] = None


def get_skill_store() -> SkillStore:
    global _skill_store
    if _skill_store is None:
        _skill_store = SkillStore()
    return _skill_store
