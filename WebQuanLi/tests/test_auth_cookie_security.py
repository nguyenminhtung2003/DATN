import asyncio
import sys
import uuid
import unittest
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth.utils import hash_password
from app.database import Base, get_db
from app.main import app
from app.models import User


class AuthCookieSecurityTest(unittest.TestCase):
    def setUp(self):
        self.db_path = Path(__file__).resolve().parents[1] / "data" / f"auth_cookie_{uuid.uuid4().hex}.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{self.db_path.as_posix()}")
        self.session_factory = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

        async def override_db():
            async with self.session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_db
        asyncio.run(self._create_schema_and_user())

    def tearDown(self):
        app.dependency_overrides.clear()
        asyncio.run(self.engine.dispose())
        self.db_path.unlink(missing_ok=True)

    async def _create_schema_and_user(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with self.session_factory() as db:
            db.add(User(username="admin", hashed_password=hash_password("secret"), role="admin"))
            await db.commit()

    def test_login_cookie_is_secure_when_request_is_https(self):
        async def run():
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="https://testserver",
                follow_redirects=False,
            ) as client:
                return await client.post("/login", data={"username": "admin", "password": "secret"})

        response = asyncio.run(run())

        self.assertEqual(response.status_code, 302)
        cookie = response.headers["set-cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("Secure", cookie)


if __name__ == "__main__":
    unittest.main()
