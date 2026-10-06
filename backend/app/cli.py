"""Manage dashboard users from the server.

    python -m app.cli create-user EMAIL [--password-stdin]
    python -m app.cli set-password EMAIL [--password-stdin]
    python -m app.cli disable-user EMAIL
    python -m app.cli list-users

Without --password-stdin the password is asked for interactively (not echoed).
In Docker: `docker compose exec api python -m app.cli create-user you@example.com`.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
from typing import TextIO

from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.core.users import create_user, find_user, set_password
from app.db.base import create_engine, session_factory
from app.db.models import User


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Manage EyesOnPlay dashboard users.")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("create-user", "set-password"):
        cmd = commands.add_parser(name)
        cmd.add_argument("email")
        cmd.add_argument("--password-stdin", action="store_true", help="read the password from standard input")
    commands.add_parser("disable-user").add_argument("email")
    commands.add_parser("list-users")
    return parser


def _password(args: argparse.Namespace, stdin: TextIO) -> str:
    if args.password_stdin:
        return stdin.readline().rstrip("\n")
    first = getpass.getpass("Password: ")
    if getpass.getpass("Repeat password: ") != first:
        raise ValueError("Passwords do not match")
    return first


async def run(argv: list[str], settings: Settings, stdin: TextIO = sys.stdin) -> int:
    args = _parser().parse_args(argv)
    engine = create_engine(settings.database_url)
    try:
        async with session_factory(engine)() as db:
            if args.command == "list-users":
                for user in await db.scalars(select(User).order_by(User.email)):
                    print(f"{user.email}{'  (disabled)' if user.disabled else ''}")
                return 0
            if args.command == "create-user":
                user = await create_user(db, args.email, _password(args, stdin))
                print(f"Created {user.email}")
                return 0
            user = await find_user(db, args.email)
            if user is None:
                raise ValueError(f"No user with email {args.email}")
            if args.command == "set-password":
                await set_password(db, user, _password(args, stdin))
                print(f"Password changed for {user.email}")
            else:
                user.disabled = True
                await db.commit()
                print(f"Disabled {user.email}")
            return 0
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        await engine.dispose()


def main() -> None:
    sys.exit(asyncio.run(run(sys.argv[1:], get_settings())))


if __name__ == "__main__":
    main()
