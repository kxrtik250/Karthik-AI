from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import Profile


async def get_default_profile(db: AsyncSession) -> Optional[Profile]:
    """Retrieve the primary profile."""
    result = await db.execute(select(Profile).limit(1))
    return result.scalars().first()
