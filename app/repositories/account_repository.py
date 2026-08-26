from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.account import WbAccount


class AccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active(self) -> WbAccount | None:
        result = await self._session.scalar(
            select(WbAccount).where(WbAccount.is_active.is_(True)).limit(1)
        )
        return cast("WbAccount | None", result)

    async def upsert_active(self, encrypted_token: str, environment: str) -> WbAccount:
        account = await self.get_active()
        if account is None:
            account = WbAccount(
                name="Default",
                encrypted_api_token=encrypted_token,
                environment=environment,
                is_active=True,
            )
            self._session.add(account)
            await self._session.flush()
            return account
        account.encrypted_api_token = encrypted_token
        account.environment = environment
        account.last_sync_error = None
        return account
