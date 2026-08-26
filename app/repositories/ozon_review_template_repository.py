from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ozon import (
    OzonReviewTemplate,
    OzonReviewTemplateKeyword,
    OzonReviewTemplateProduct,
    OzonReviewTemplateRating,
)
from app.services.ozon_review_matching_service import normalize_ozon_review_text
from app.services.ozon_review_template_catalog import (
    OzonReviewTemplateCandidate,
    OzonReviewTemplateDefinition,
)


class OzonReviewTemplateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_active_candidates(self) -> list[OzonReviewTemplateCandidate]:
        templates = (
            await self._session.scalars(
                select(OzonReviewTemplate).where(OzonReviewTemplate.is_active.is_(True))
            )
        ).all()
        candidates: list[OzonReviewTemplateCandidate] = []
        for template in templates:
            keywords = (
                await self._session.scalars(
                    select(OzonReviewTemplateKeyword.normalized_keyword).where(
                        OzonReviewTemplateKeyword.template_id == template.id
                    )
                )
            ).all()
            products = (
                await self._session.scalars(
                    select(OzonReviewTemplateProduct.offer_id).where(
                        OzonReviewTemplateProduct.template_id == template.id
                    )
                )
            ).all()
            ratings = (
                await self._session.scalars(
                    select(OzonReviewTemplateRating.rating).where(
                        OzonReviewTemplateRating.template_id == template.id
                    )
                )
            ).all()
            candidates.append(
                OzonReviewTemplateCandidate(
                    id=template.id,
                    code=template.code,
                    name=template.name,
                    category=template.category,
                    text=template.text,
                    priority=template.priority,
                    ratings=set(ratings),
                    keywords=set(keywords),
                    offer_ids=set(products),
                    auto_send=template.auto_send,
                    is_default=template.category == "default",
                )
            )
        return candidates

    async def seed(self, definitions: tuple[OzonReviewTemplateDefinition, ...]) -> None:
        existing_templates = {
            existing_template.code: existing_template
            for existing_template in (await self._session.scalars(select(OzonReviewTemplate))).all()
        }
        definition_codes = {definition.code for definition in definitions}
        for existing_template in existing_templates.values():
            if existing_template.code not in definition_codes:
                existing_template.is_active = False
        for definition in definitions:
            template = existing_templates.get(definition.code)
            if template is None:
                template = OzonReviewTemplate(
                    code=definition.code,
                    name=definition.name,
                    category=definition.category,
                    text=definition.text,
                    priority=definition.priority,
                    is_active=definition.is_active,
                    auto_send=definition.auto_send,
                )
                self._session.add(template)
                await self._session.flush()
            else:
                template.name = definition.name
                template.category = definition.category
                template.text = definition.text
                template.priority = definition.priority
                template.is_active = definition.is_active
                template.auto_send = definition.auto_send
            await self._session.execute(
                delete(OzonReviewTemplateKeyword).where(
                    OzonReviewTemplateKeyword.template_id == template.id
                )
            )
            await self._session.execute(
                delete(OzonReviewTemplateProduct).where(
                    OzonReviewTemplateProduct.template_id == template.id
                )
            )
            await self._session.execute(
                delete(OzonReviewTemplateRating).where(
                    OzonReviewTemplateRating.template_id == template.id
                )
            )
            seen_keywords: set[str] = set()
            keyword_rows: list[OzonReviewTemplateKeyword] = []
            for keyword in definition.keywords:
                normalized_keyword = normalize_ozon_review_text(keyword)
                if normalized_keyword in seen_keywords:
                    continue
                seen_keywords.add(normalized_keyword)
                keyword_rows.append(
                    OzonReviewTemplateKeyword(
                        template_id=template.id,
                        keyword=keyword,
                        normalized_keyword=normalized_keyword,
                    )
                )
            self._session.add_all(keyword_rows)
            self._session.add_all(
                OzonReviewTemplateProduct(template_id=template.id, offer_id=offer_id)
                for offer_id in definition.offer_ids
            )
            self._session.add_all(
                OzonReviewTemplateRating(template_id=template.id, rating=rating)
                for rating in definition.ratings
            )
