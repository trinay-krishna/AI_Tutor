"""Create an admin user, or promote an existing user to admin.

Usage:
    uv run python -m src.scripts.create_admin --email admin@example.com
"""

import argparse
import asyncio
import getpass

from sqlalchemy import select

from src.db import AsyncSessionLocal
from src.models import User, UserRole
from src.services.security import hash_password


async def create_admin(email: str, password: str | None) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is not None:
            user.role = UserRole.admin
            await db.commit()
            print(f"Existing user {email} promoted to admin.")
            return

        if not password:
            password = getpass.getpass("Password for new admin: ")
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                raise SystemExit("Passwords do not match.")

        user = User(email=email, password_hash=hash_password(password), role=UserRole.admin)
        db.add(user)
        await db.commit()
        print(f"Admin user {email} created.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", default=None, help="If omitted, you'll be prompted.")
    args = parser.parse_args()
    asyncio.run(create_admin(args.email, args.password))


if __name__ == "__main__":
    main()
