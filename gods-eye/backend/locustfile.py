"""Load testing for God's Eye API.

Usage:
    pip install locust
    locust -f locustfile.py --host http://localhost:8000

Then open http://localhost:8089 in your browser to start the test.
"""

from locust import HttpUser, task, between
import random


class GodsEyeUser(HttpUser):
    """Simulates a user interacting with God's Eye simulation API."""

    wait_time = between(1, 3)

    def on_start(self):
        """Initialize test data on user start."""
        self.scenarios = [
            "rbi_rate_cut",
            "rbi_rate_hike",
            "fii_selling",
            "fii_buying",
            "dii_buying",
            "fed_hawkish",
            "fed_dovish",
            "geopolitical_tension",
            "market_crash",
            "steady_state",
        ]

    @task(1)
    def health_check(self):
        """Hit the health endpoint (no auth required)."""
        self.client.get("/api/health")

    @task(2)
    def get_presets(self):
        """Fetch available preset scenarios."""
        self.client.get("/api/presets")

    @task(2)
    def get_history(self):
        """Fetch simulation history with pagination."""
        limit = random.choice([10, 20, 50])
        offset = random.choice([0, 20, 40])
        self.client.get(f"/api/history?limit={limit}&offset={offset}")

    @task(1)
    def get_settings(self):
        """Fetch current simulation settings."""
        self.client.get("/api/settings")

    @task(1)
    def get_metrics(self):
        """Get accuracy metrics for recent predictions."""
        lookback = random.choice([7, 30, 90])
        self.client.get(f"/api/metrics?lookback_days={lookback}")

    @task(3)
    def get_live_market(self):
        """Get current live market snapshot."""
        self.client.get("/api/market/live")

    @task(2)
    def get_options_data(self):
        """Get options chain summary."""
        symbol = random.choice(["NIFTY", "SENSEX", "NIFTYNXT50"])
        self.client.get(f"/api/market/options?symbol={symbol}")

    @task(1)
    def get_sectors(self):
        """Get sector index values."""
        self.client.get("/api/market/sectors")

    @task(5)
    def run_simulation_with_flat_fields(self):
        """Run simulation with flat market fields (backwards compatible)."""
        # Realistic India market values
        self.client.post("/api/simulate", json={
            "nifty_spot": random.uniform(23000, 24000),
            "india_vix": random.uniform(12, 20),
            "fii_flow_5d": random.uniform(-2000, 2000),
            "dii_flow_5d": random.uniform(-1000, 1500),
            "usd_inr": random.uniform(83, 84),
            "dxy": random.uniform(103, 105),
            "pcr_index": random.uniform(0.8, 1.2),
            "max_pain": random.uniform(23000, 24000),
            "dte": random.randint(1, 25),
            "context": random.choice(["normal", "expiry", "budget", "election"])
        })

    @task(8)
    def run_simulation_with_preset(self):
        """Run simulation using a preset scenario."""
        scenario_id = random.choice(self.scenarios)
        self.client.post("/api/simulate", json={
            "scenario_id": scenario_id
        })

    @task(2)
    def run_simulation_live(self):
        """Run simulation with live market data from NSE."""
        self.client.post("/api/simulate", json={
            "source": "live"
        })

    @task(1)
    def get_agent_details(self):
        """Get details for a specific agent."""
        agent_id = random.choice(["fii", "dii", "retail_fno", "algo", "promoter", "rbi"])
        self.client.get(f"/api/agent/{agent_id}")

    @task(1)
    def get_agent_accuracy(self):
        """Get accuracy metrics for a specific agent."""
        agent_id = random.choice(["fii", "dii", "retail_fno", "algo", "promoter", "rbi"])
        days = random.choice([7, 30, 60])
        self.client.get(f"/api/agent/{agent_id}/accuracy?days={days}")

    @task(1)
    def get_feedback_weights(self):
        """Get accuracy-tuned agent weights vs base weights."""
        days = random.choice([30, 60, 90])
        self.client.get(f"/api/feedback/weights?days={days}")

    @task(2)
    def run_simulation_with_nested_market_input(self):
        """Run simulation with nested market_input object."""
        self.client.post("/api/simulate", json={
            "market_input": {
                "nifty_spot": random.uniform(23000, 24000),
                "india_vix": random.uniform(12, 20),
                "fii_flow_5d": random.uniform(-2000, 2000),
                "dii_flow_5d": random.uniform(-1000, 1500),
                "usd_inr": random.uniform(83, 84),
                "dxy": random.uniform(103, 105),
                "pcr_index": random.uniform(0.8, 1.2),
                "max_pain": random.uniform(23000, 24000),
                "dte": random.randint(1, 25),
                "context": "normal"
            }
        })
