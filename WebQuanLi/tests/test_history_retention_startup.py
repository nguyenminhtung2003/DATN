import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app, lifespan


class StartupRetentionTest(unittest.TestCase):
    def test_lifespan_purges_old_alerts_after_database_init(self):
        calls = []

        async def fake_init_db():
            calls.append(("init", None))

        async def fake_purge_old_alerts(db):
            calls.append(("purge", db))
            return 3

        class FakeSession:
            async def __aenter__(self):
                calls.append(("session_enter", None))
                return "fake-db"

            async def __aexit__(self, exc_type, exc, tb):
                calls.append(("session_exit", None))

        async def run_lifespan():
            with (
                patch("app.main.init_db", fake_init_db),
                patch("app.main.async_session_factory", lambda: FakeSession(), create=True),
                patch("app.main.purge_old_alerts", fake_purge_old_alerts, create=True),
            ):
                async with lifespan(app):
                    calls.append(("ready", None))

        asyncio.run(run_lifespan())

        self.assertEqual(
            calls,
            [
                ("init", None),
                ("session_enter", None),
                ("purge", "fake-db"),
                ("session_exit", None),
                ("ready", None),
            ],
        )
