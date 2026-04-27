import asyncio
import sys
import unittest
from pathlib import Path

from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth.dependencies import get_current_user
from app.main import app
from app.models import User


class BankingUIContractTest(unittest.TestCase):
    def test_dashboard_exposes_trust_banking_theme_hooks(self):
        async def run():
            app.dependency_overrides[get_current_user] = lambda: User(username="test", role="admin")
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/")
            app.dependency_overrides.clear()
            return response

        response = asyncio.run(run())

        self.assertEqual(response.status_code, 200)
        self.assertIn("trust-banking-dashboard", response.text)
        self.assertIn("TRUST SAFETY OVERVIEW", response.text)
        self.assertIn("overview-chip", response.text)
        self.assertIn("sidebar-is-collapsed", response.text)
        self.assertIn('id="nav-fleet"', response.text)
        self.assertIn('id="nav-statistics"', response.text)
        self.assertIn('id="nav-docs"', response.text)
        self.assertIn('target="_blank"', response.text)
        self.assertIn('rel="noopener noreferrer"', response.text)

    def test_sidebar_css_keeps_fixed_navigation_foundation(self):
        css = Path(__file__).resolve().parents[1].joinpath("static", "css", "style.css").read_text(
            encoding="utf-8"
        )

        self.assertIn("Sidebar foundation reset", css)
        self.assertIn("Banking sidebar shell", css)
        self.assertIn("position: fixed !important", css)
        self.assertIn("backdrop-filter: blur(24px)", css)


if __name__ == "__main__":
    unittest.main()
