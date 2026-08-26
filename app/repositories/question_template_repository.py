from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.question import (
    QuestionTemplate,
    QuestionTemplateKeyword,
    QuestionTemplateProduct,
)
from app.services.question_matching_service import normalize_question_text
from app.services.question_template_catalog import (
    QuestionTemplateCandidate,
    QuestionTemplateDefinition,
)


class QuestionTemplateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_active_candidates(self) -> list[QuestionTemplateCandidate]:
        templates = (
            await self._session.scalars(
                select(QuestionTemplate).where(QuestionTemplate.is_active.is_(True))
            )
        ).all()
        candidates: list[QuestionTemplateCandidate] = []
        for template in templates:
            keywords = (
                await self._session.scalars(
                    select(QuestionTemplateKeyword.normalized_keyword).where(
                        QuestionTemplateKeyword.template_id == template.id
                    )
                )
            ).all()
            products = (
                await self._session.scalars(
                    select(QuestionTemplateProduct.nm_id).where(
                        QuestionTemplateProduct.template_id == template.id
                    )
                )
            ).all()
            candidates.append(
                QuestionTemplateCandidate(
                    id=template.id,
                    code=template.code,
                    name=template.name,
                    category=template.category,
                    text=template.text,
                    priority=template.priority,
                    keywords=set(keywords),
                    products=set(products),
                    auto_send=template.auto_send,
                )
            )
        return candidates

    async def seed(self, definitions: tuple[QuestionTemplateDefinition, ...]) -> None:
        existing_templates = {
            existing_template.code: existing_template
            for existing_template in (await self._session.scalars(select(QuestionTemplate))).all()
        }
        definition_codes = {definition.code for definition in definitions}
        for existing_template in existing_templates.values():
            if existing_template.code not in definition_codes:
                existing_template.is_active = False
        for definition in definitions:
            template = existing_templates.get(definition.code)
            if template is None:
                template = QuestionTemplate(
                    code=definition.code,
                    name=definition.name,
                    category=definition.category,
                    text=definition.text,
                    priority=definition.priority,
                    is_active=True,
                    auto_send=definition.auto_send,
                )
                self._session.add(template)
                await self._session.flush()
            else:
                template.name = definition.name
                template.category = definition.category
                template.text = definition.text
                template.priority = definition.priority
                template.is_active = True
                template.auto_send = definition.auto_send
            await self._session.execute(
                delete(QuestionTemplateKeyword).where(
                    QuestionTemplateKeyword.template_id == template.id
                )
            )
            await self._session.execute(
                delete(QuestionTemplateProduct).where(
                    QuestionTemplateProduct.template_id == template.id
                )
            )
            keyword_rows: list[QuestionTemplateKeyword] = []
            seen_keywords: set[str] = set()
            for keyword in definition.keywords:
                normalized_keyword = normalize_question_text(keyword)
                if normalized_keyword in seen_keywords:
                    continue
                seen_keywords.add(normalized_keyword)
                keyword_rows.append(
                    QuestionTemplateKeyword(
                        template_id=template.id,
                        keyword=keyword,
                        normalized_keyword=normalized_keyword,
                    )
                )
            self._session.add_all(keyword_rows)
            self._session.add_all(
                QuestionTemplateProduct(template_id=template.id, nm_id=nm_id)
                for nm_id in definition.products
            )
