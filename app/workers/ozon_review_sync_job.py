from app.config import get_settings
from app.db.session import SessionFactory
from app.integrations.ozon.client import OzonClient
from app.integrations.ozon.exceptions import OzonAuthError, OzonRequestError
from app.repositories.ozon_account_repository import OzonAccountRepository
from app.repositories.ozon_review_action_repository import OzonReviewActionRepository
from app.repositories.ozon_review_repository import OzonReviewRepository
from app.repositories.ozon_review_template_repository import OzonReviewTemplateRepository
from app.services.encryption_service import EncryptionService
from app.services.ozon_review_matching_service import OzonReviewMatchingService
from app.services.ozon_review_rendering_service import OzonReviewAnswerRenderer
from app.services.ozon_review_sync_service import OzonReviewSyncService
from app.services.ozon_review_template_catalog import STARTER_OZON_REVIEW_TEMPLATES


async def run_ozon_review_sync_once() -> tuple[int, int, int]:
    settings = get_settings()
    async with SessionFactory() as session:
        templates = OzonReviewTemplateRepository(session)
        await templates.seed(STARTER_OZON_REVIEW_TEMPLATES)
        account_repo = OzonAccountRepository(session)
        account = await account_repo.get_active()
        if settings.ozon_client_id and settings.ozon_api_key:
            encrypted_api_key = EncryptionService(settings.app_encryption_key).encrypt(
                settings.ozon_api_key
            )
            account = await account_repo.upsert_active(
                settings.ozon_client_id,
                encrypted_api_key,
                settings.ozon_environment,
            )
        if account is None:
            await session.commit()
            return (0, 0, 0)
        await session.commit()
        api_key = EncryptionService(settings.app_encryption_key).decrypt(account.encrypted_api_key)
        client = OzonClient(
            settings.ozon_api_base_url,
            account.client_id,
            api_key,
            max_retries=settings.ozon_http_max_retries,
            connect_timeout=settings.ozon_http_connect_timeout,
            read_timeout=settings.ozon_http_read_timeout,
        )
        try:
            result = await OzonReviewSyncService(
                account,
                client,
                OzonReviewRepository(session),
                templates,
                OzonReviewActionRepository(session),
                OzonReviewMatchingService(),
                OzonReviewAnswerRenderer(settings.brand_name, settings.answer_signature),
            ).sync()
            await session.commit()
            return result
        except OzonAuthError as exc:
            suffix = f":{exc.detail}" if exc.detail else ""
            account.last_sync_error = f"OzonAuthError:{exc.status_code}{suffix}"[:500]
            await session.commit()
            raise
        except OzonRequestError as exc:
            suffix = f":{exc.detail}" if exc.detail else ""
            account.last_sync_error = f"OzonRequestError:{exc.status_code}{suffix}"[:500]
            await session.commit()
            raise
        except Exception as exc:
            account.last_sync_error = type(exc).__name__
            await session.commit()
            raise
        finally:
            await client.aclose()
