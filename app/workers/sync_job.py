from app.config import get_settings
from app.db.session import SessionFactory
from app.integrations.wildberries.client import WildberriesClient
from app.repositories.account_repository import AccountRepository
from app.repositories.action_repository import ActionRepository
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.template_repository import TemplateRepository
from app.services.encryption_service import EncryptionService
from app.services.matching_service import MatchingService
from app.services.rendering_service import AnswerRenderer
from app.services.sync_service import SyncService
from app.services.template_catalog import STARTER_TEMPLATES


async def run_sync_once() -> tuple[int, int, int]:
    settings = get_settings()
    async with SessionFactory() as session:
        templates = TemplateRepository(session)
        await templates.seed(STARTER_TEMPLATES)
        account_repo = AccountRepository(session)
        account = await account_repo.get_active()
        if settings.wb_api_token:
            encrypted = EncryptionService(settings.app_encryption_key).encrypt(
                settings.wb_api_token
            )
            account = await account_repo.upsert_active(encrypted, settings.wb_environment)
        if account is None:
            await session.commit()
            return (0, 0, 0)
        await session.commit()
        token = EncryptionService(settings.app_encryption_key).decrypt(account.encrypted_api_token)
        client = WildberriesClient(
            settings.wb_api_base_url,
            token,
            max_retries=settings.http_max_retries,
            connect_timeout=settings.http_connect_timeout,
            read_timeout=settings.http_read_timeout,
            min_interval_seconds=settings.wb_api_min_interval_seconds,
        )
        try:
            result = await SyncService(
                account,
                client,
                FeedbackRepository(session),
                templates,
                ActionRepository(session),
                MatchingService(),
                AnswerRenderer(settings.brand_name, settings.answer_signature),
            ).sync()
            await session.commit()
            return result
        finally:
            await client.aclose()
