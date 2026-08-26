from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ozon import OzonAccount


class OzonAccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active(self) -> OzonAccount | None:
        result = await self._session.scalar(
            select(OzonAccount).where(OzonAccount.is_active.is_(True)).limit(1)
        )
        return cast("OzonAccount | None", result)

    async def upsert_active(
        self, client_id: str, encrypted_api_key: str, environment: str
    ) -> OzonAccount:
        account = await self.get_active()
        if account is None:
            account = OzonAccount(
                name="Default",
                client_id=client_id,
                encrypted_api_key=encrypted_api_key,
                environment=environment,
                is_active=True,
            )
            self._session.add(account)
            await self._session.flush()
            return account
        account.client_id = client_id
        account.encrypted_api_key = encrypted_api_key
        account.environment = environment
        account.last_sync_error = None
        return account
