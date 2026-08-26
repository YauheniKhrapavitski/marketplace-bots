from dataclasses import dataclass, field

from app.services.template_catalog import STARTER_TEMPLATES


@dataclass(frozen=True)
class OzonReviewTemplateDefinition:
    code: str
    name: str
    category: str
    text: str
    priority: int = 0
    ratings: tuple[int, ...] = ()
    keywords: tuple[str, ...] = ()
    offer_ids: tuple[str, ...] = ()
    auto_send: bool = False
    is_default: bool = False
    is_active: bool = True


@dataclass
class OzonReviewTemplateCandidate:
    id: int
    code: str
    name: str
    category: str
    text: str
    priority: int
    ratings: set[int] = field(default_factory=set)
    keywords: set[str] = field(default_factory=set)
    offer_ids: set[str] = field(default_factory=set)
    auto_send: bool = False
    is_default: bool = False


ACTIVE_WB_COMPAT_OZON_REVIEW_TEMPLATES: tuple[OzonReviewTemplateDefinition, ...] = tuple(
    OzonReviewTemplateDefinition(
        code=f"ozon_{template.code}",
        name=f"Ozon {template.name}",
        category=template.category,
        text=template.text,
        priority=template.priority,
        ratings=template.ratings,
        keywords=template.keywords,
        auto_send=template.category == "positive",
        is_default=template.is_default,
    )
    for template in STARTER_TEMPLATES
)

INACTIVE_WB_COMPAT_OZON_REVIEW_TEMPLATES: tuple[OzonReviewTemplateDefinition, ...] = (
    OzonReviewTemplateDefinition(
        code="ozon_item_damage",
        name="Ozon Товар повреждён",
        category="damage",
        text=(
            "{{buyer_greeting}} Нам жаль, что вы получили товар с повреждением или "
            "неисправностью. Пожалуйста, оформите возврат через личный кабинет "
            "Wildberries, если это доступно для заказа. Информацию о проблеме мы "
            "передадим на проверку. {{signature}}"
        ),
        priority=100,
        keywords=(
            "брак",
            "дефект",
            "не работает",
            "поврежден",
            "разбит",
            "сломан",
            "трещина",
        ),
        is_active=False,
    ),
    OzonReviewTemplateDefinition(
        code="ozon_rating_1_2_negative",
        name="Ozon Одна или две звезды",
        category="negative",
        text=(
            "{{buyer_greeting}} Нам жаль, что товар «{{product_name}}» не оправдал "
            "ваших ожиданий. Спасибо, что сообщили о проблеме. Мы передадим "
            "информацию ответственному сотруднику и учтём её при дальнейшей работе. "
            "{{signature}}"
        ),
        priority=8,
        ratings=(1, 2),
        is_active=False,
    ),
    OzonReviewTemplateDefinition(
        code="ozon_rating_3_neutral",
        name="Ozon Три звезды",
        category="neutral",
        text=(
            "{{buyer_greeting}} Спасибо, что поделились впечатлением о товаре "
            "«{{product_name}}». Нам важно понять, что можно улучшить. Мы "
            "обязательно учтём ваш комментарий. {{signature}}"
        ),
        priority=8,
        ratings=(3,),
        is_active=False,
    ),
)

STARTER_OZON_REVIEW_TEMPLATES = (
    ACTIVE_WB_COMPAT_OZON_REVIEW_TEMPLATES + INACTIVE_WB_COMPAT_OZON_REVIEW_TEMPLATES
)
