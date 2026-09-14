"""Promote or demote a user's role.

Usage:
    uv run python -m src.scripts.promote_user --email user@example.com --role admin
"""

import argparse
import asyncio

from sqlalchemy import select

from src.db import AsyncSessionLocal
from src.models import User, UserRole


async def set_role(email: str, role: UserRole) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            raise SystemExit(f"No user with email {email}")
        user.role = role
        await db.commit()
        print(f"{email} is now {role.value}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--role", choices=[r.value for r in UserRole], required=True)
    args = parser.parse_args()
    asyncio.run(set_role(args.email, UserRole(args.role)))


if __name__ == "__main__":
    main()
