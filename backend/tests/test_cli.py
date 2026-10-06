"""`python -m app.cli`: manage dashboard users from the server."""

from __future__ import annotations

import io

from sqlalchemy import select

from app.cli import run
from app.core.passwords import verify_password
from app.db.models import User


async def test_create_user_reads_the_password_from_stdin(app, settings):
    code = await run(["create-user", "coach@example.com", "--password-stdin"], settings, stdin=io.StringIO("a-long-password\n"))

    assert code == 0
    async with app.state.session_factory() as db:
        user = (await db.scalars(select(User).where(User.email == "coach@example.com"))).one()
    assert verify_password(user.password_hash, "a-long-password")


async def test_set_password_and_disable(app, settings):
    await run(["create-user", "coach@example.com", "--password-stdin"], settings, stdin=io.StringIO("a-long-password\n"))

    assert await run(["set-password", "coach@example.com", "--password-stdin"], settings, stdin=io.StringIO("another-password\n")) == 0
    assert await run(["disable-user", "coach@example.com"], settings) == 0

    async with app.state.session_factory() as db:
        user = (await db.scalars(select(User).where(User.email == "coach@example.com"))).one()
    assert verify_password(user.password_hash, "another-password") and user.disabled


async def test_errors_return_a_non_zero_code(app, settings, capsys):
    assert await run(["disable-user", "nobody@example.com"], settings) == 1
    assert "no user" in capsys.readouterr().err.lower()
