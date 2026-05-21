"""
Shared FastAPI dependencies.
"""
from typing import AsyncGenerator

from fastapi import Header

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal, AsyncSession

settings = get_settings()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_tenant_id(x_tenant_id: str = Header(default=None)) -> str:
    """
    Multi-tenancy stub: reads tenant from X-Tenant-ID header.
    Falls back to default tenant. Replace with real auth when ready.
    """
    return x_tenant_id or settings.default_tenant_id
