"""Seed script: populate the SkillStore with hand-authored skills per key agent.

Run directly to seed:
    GODS_EYE_LEARNING_SKILL_DIR=/app/skills python -m app.learning.seed_skills
    python -m app.learning.seed_skills --dir /tmp/skills

Or import and call seed_all() programmatically:
    from app.learning.seed_skills import seed_all
    count = seed_all('/tmp/skills')  # returns number of new skills saved
"""

from app.learning.skill_store import Skill, SkillStore

# ─── Seed skills ──────────────────────────────────────────────────────────────

SEED_SKILLS = [
    Skill(
        name="High VIX Caution",
        agent="FII",
        description="FII agent should reduce conviction when India VIX exceeds 20",
        content=(
            "When India VIX exceeds 20, FII redemption pressure tends to accelerate as risk managers "
            "trigger stop-losses on EM allocations. Historical pattern shows FII selling intensity "
            "increases by 30-40% above VIX 20. Lower conviction by 10-15% on any BUY call. "
            "Above VIX 25, prefer HOLD over BUY regardless of flow signals."
        ),
        trigger_conditions=["india_vix > 20"],
        created="2026-03-30T00:00:00",
        updated="2026-03-30T00:00:00",
        success_rate=0.0,
        times_applied=0,
    ),
    Skill(
        name="SIP Absorption",
        agent="DII",
        description="DII agent should increase conviction when absorbing heavy FII outflows via SIP inflows",
        content=(
            "When FII 5-day outflows exceed $100M and DII flows are positive, DII SIP deployment is "
            "absorbing selling pressure. Historical data shows this pattern precedes 2-3% index recovery "
            "over 5-10 sessions. Increase conviction on BUY calls by 10% when this absorption pattern "
            "is active. The pattern is most reliable when FII outflows are spread over multiple sessions "
            "rather than concentrated in a single day."
        ),
        trigger_conditions=["fii_flow_5d < -100", "dii_flow_5d > 50"],
        created="2026-03-30T00:00:00",
        updated="2026-03-30T00:00:00",
        success_rate=0.0,
        times_applied=0,
    ),
    Skill(
        name="Max Pain Pull",
        agent="RETAIL_FNO",
        description="Within 2 days of expiry, Nifty gravitates toward max pain level",
        content=(
            "Within 2 days of expiry, Nifty tends to gravitate toward max pain level as market makers "
            "pin positions. If spot is 1.5% or more away from max pain, the probability of mean reversion "
            "to max pain exceeds 60%. Favor the direction of max pain when DTE <= 2. This gravitational "
            "pull is strongest in the final 90 minutes of trading and weakens significantly if India VIX "
            "is above 22, in which case reduce the max pain weight by 50%."
        ),
        trigger_conditions=["dte <= 2"],
        created="2026-03-30T00:00:00",
        updated="2026-03-30T00:00:00",
        success_rate=0.0,
        times_applied=0,
    ),
    Skill(
        name="PCR Reversal Signal",
        agent="ALGO",
        description="PCR above 1.3 marks a contrarian buy zone for the Algo model",
        content=(
            "PCR above 1.3 indicates heavy put buying which historically marks a contrarian buy zone for "
            "the Algo model. Mean reversion signal strength increases with PCR — above 1.5 the signal is "
            "strongest. Weight the PCR score 1.2x when PCR exceeds 1.3, and 1.4x when PCR exceeds 1.5. "
            "Combine with DII flow direction for confirmation: PCR reversal + positive DII flows historically "
            "yields 68% accuracy on 2-session forward returns."
        ),
        trigger_conditions=["pcr_index > 1.3"],
        created="2026-03-30T00:00:00",
        updated="2026-03-30T00:00:00",
        success_rate=0.0,
        times_applied=0,
    ),
    Skill(
        name="Pre-Expiry Caution",
        agent="ALL",
        description="All agents should reduce conviction on expiry day with elevated VIX",
        content=(
            "On expiry day with VIX above 18, all agents should reduce conviction by 15-20%. Gamma exposure "
            "creates erratic intraday swings that do not reflect fundamental direction. This applies "
            "universally across agent types. The effect is compounded when the USD/INR is trending "
            "aggressively in either direction — add another 5% conviction reduction if USD/INR moved "
            "more than 0.5% in the prior session. Resume normal conviction weighting in the next session."
        ),
        trigger_conditions=["dte <= 1", "india_vix > 18"],
        created="2026-03-30T00:00:00",
        updated="2026-03-30T00:00:00",
        success_rate=0.0,
        times_applied=0,
    ),
]


def seed_all(base_dir: str = None) -> int:
    """Seed the SkillStore with hand-authored skills.

    Idempotent — skips skills that already exist in the store by name.

    Args:
        base_dir: Base directory for the SkillStore. Defaults to config value.

    Returns:
        Number of new skills saved (0 if all already present).
    """
    store = SkillStore(base_dir)

    # Build set of existing skill names for idempotency check
    existing = {s.name for s in store.load_skills()}

    saved = 0
    for skill in SEED_SKILLS:
        if skill.name in existing:
            continue
        store.save_skill(skill)
        saved += 1

    return saved


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Seed the SkillStore with hand-authored skills.")
    parser.add_argument(
        "--dir",
        default=None,
        metavar="PATH",
        help="Base directory for the SkillStore (default: from GODS_EYE_LEARNING_SKILL_DIR env or config)",
    )
    args = parser.parse_args()

    count = seed_all(args.dir)
    if count > 0:
        print(f"Seeded {count} skill(s) into the store.")
    else:
        print("All skills already present — nothing to seed.")
