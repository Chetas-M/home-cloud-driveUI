import asyncio
from app.database import async_session
from app.models import User
from app.auth import get_password_hash

async def test_create_user():
    async with async_session() as db:
        try:
            new_user = User(
                email="test3@example.com",
                username="testuser3",
                password_hash=get_password_hash("password123"),
                storage_quota=107374182400,
            )
            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)
            print(f"SUCCESS: Created user {new_user.id} - {new_user.email}")
        except Exception as e:
            print(f"ERROR: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

asyncio.run(test_create_user())
