from app.config import get_settings
from app.db.session import SessionFactory
from app.integrations.wildberries.questions_client import WildberriesQuestionsClient
from app.repositories.account_repository import AccountRepository
from app.repositories.question_action_repository import QuestionActionRepository
from app.repositories.question_repository import QuestionRepository
from app.repositories.question_template_repository import QuestionTemplateRepository
from app.services.encryption_service import EncryptionService
from app.services.question_matching_service import QuestionMatchingService
from app.services.question_rendering_service import QuestionAnswerRenderer
from app.services.question_sync_service import QuestionSyncService
from app.services.question_template_catalog import STARTER_QUESTION_TEMPLATES


async def run_question_sync_once() -> tuple[int, int, int]:
    settings = get_settings()
    async with SessionFactory() as session:
        templates = QuestionTemplateRepository(session)
        await templates.seed(STARTER_QUESTION_TEMPLATES)
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
        client = WildberriesQuestionsClient(
            settings.wb_api_base_url,
            token,
            max_retries=settings.http_max_retries,
            connect_timeout=settings.http_connect_timeout,
            read_timeout=settings.http_read_timeout,
            min_interval_seconds=settings.wb_api_min_interval_seconds,
        )
        try:
            result = await QuestionSyncService(
                account,
                client,
                QuestionRepository(session),
                templates,
                QuestionActionRepository(session),
                QuestionMatchingService(),
                QuestionAnswerRenderer(),
                auto_send_enabled=settings.question_auto_send_enabled,
            ).sync(page_size=50, inter_page_delay_seconds=1.5)
            await session.commit()
            return result
        finally:
            await client.aclose()
