from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.template import Template, TemplateKeyword, TemplateProduct, TemplateRating
from app.services.matching_service import normalize_feedback_text
from app.services.template_catalog import TemplateCandidate, TemplateDefinition


class TemplateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_active_candidates(self) -> list[TemplateCandidate]:
        result = await self._session.scalars(
            select(Template)
            .where(Template.is_active.is_(True))
            .options(
                selectinload(Template.ratings),
                selectinload(Template.keywords),
                selectinload(Template.products),
            )
        )
        return [self._to_candidate(template) for template in result.all()]

    async def seed(self, definitions: tuple[TemplateDefinition, ...]) -> None:
        existing_templates = {
            existing_template.code: existing_template
            for existing_template in (await self._session.scalars(select(Template))).all()
        }
        definition_codes = {definition.code for definition in definitions}
        for existing_template in existing_templates.values():
            if existing_template.code not in definition_codes:
                existing_template.is_active = False
        for definition in definitions:
            template = existing_templates.get(definition.code)
            if template is None:
                template = Template(
                    code=definition.code,
                    name=definition.name,
                    category=definition.category,
                    text=definition.text,
                    priority=definition.priority,
                    is_active=True,
                    is_default=definition.is_default,
                )
                self._session.add(template)
                await self._session.flush()
            else:
                template.name = definition.name
                template.category = definition.category
                template.text = definition.text
                template.priority = definition.priority
                template.is_active = True
                template.is_default = definition.is_default
            await self._session.execute(
                delete(TemplateRating).where(TemplateRating.template_id == template.id)
            )
            await self._session.execute(
                delete(TemplateKeyword).where(TemplateKeyword.template_id == template.id)
            )
            await self._session.execute(
                delete(TemplateProduct).where(TemplateProduct.template_id == template.id)
            )
            self._session.add_all(
                TemplateRating(template_id=template.id, rating=rating)
                for rating in definition.ratings
            )
            keyword_rows: list[TemplateKeyword] = []
            seen_keywords: set[str] = set()
            for keyword in definition.keywords:
                normalized_keyword = normalize_feedback_text(keyword)
                if normalized_keyword in seen_keywords:
                    continue
                seen_keywords.add(normalized_keyword)
                keyword_rows.append(
                    TemplateKeyword(
                        template_id=template.id,
                        keyword=keyword,
                        normalized_keyword=normalized_keyword,
                    )
                )
            self._session.add_all(keyword_rows)
            self._session.add_all(
                TemplateProduct(template_id=template.id, nm_id=nm_id)
                for nm_id in definition.products
            )

    @staticmethod
    def _to_candidate(template: Template) -> TemplateCandidate:
        return TemplateCandidate(
            id=template.id,
            code=template.code,
            name=template.name,
            category=template.category,
            text=template.text,
            priority=template.priority,
            ratings={item.rating for item in template.ratings},
            keywords={item.normalized_keyword for item in template.keywords},
            products={item.nm_id for item in template.products},
            is_default=template.is_default,
        )
