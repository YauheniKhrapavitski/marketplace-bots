from dataclasses import dataclass, field


@dataclass(frozen=True)
class QuestionTemplateDefinition:
    code: str
    name: str
    category: str
    text: str
    priority: int = 0
    keywords: tuple[str, ...] = ()
    products: tuple[int, ...] = ()
    auto_send: bool = False


@dataclass
class QuestionTemplateCandidate:
    id: int
    code: str
    name: str
    category: str
    text: str
    priority: int
    keywords: set[str] = field(default_factory=set)
    products: set[int] = field(default_factory=set)
    auto_send: bool = False


STARTER_QUESTION_TEMPLATES: tuple[QuestionTemplateDefinition, ...] = (
    QuestionTemplateDefinition(
        code="film_request",
        name="Запрос на пленку",
        category="film",
        keywords=(
            "пленка",
            "плёнка",
            "какая пленка",
            "какая плёнка",
            "материал",
            "spectroll",
            "толщина",
            "микрон",
            "срок службы",
        ),
        priority=90,
        text="Добрый день\nПленка Spectroll PPF TPH\n180-185 микрон.\nСрок службы более 7 лет",
    ),
    QuestionTemplateDefinition(
        code="instruction",
        name="Инструкция",
        category="instruction",
        keywords=(
            "инструкция",
            "видеоинструкция",
            "видео инструкция",
            "как клеить",
            "как установить",
            "установка",
            "монтаж",
            "qr",
            "qr-код",
            "vinylstudio",
        ),
        priority=80,
        text=(
            "Добрый день\n"
            "На Рутуб есть наш канал с видеоинструкциями.\n"
            "Их вы можете найти по поисковому запросу Vinylstudio. А также в каждой упаковке "
            "с товаром есть вкладыш, на котором изображен QR-код на видеоинструкции"
        ),
    ),
    QuestionTemplateDefinition(
        code="not_available",
        name="Не в наличии",
        category="availability",
        keywords=(
            "есть на",
            "нет на",
            "в наличии",
            "лекала на",
            "лекало на",
            "делаете на",
            "можно на",
            "ищу на",
            "для автомобиля",
        ),
        priority=20,
        auto_send=False,
        text="Здравствуйте!\nНа интересующий вас автомобиль у нас нет лекал",
    ),
    QuestionTemplateDefinition(
        code="fits",
        name="Да подходит",
        category="fitment",
        keywords=(
            "подойдет",
            "подойдёт",
            "подходит",
            "совместим",
            "на мой автомобиль",
            "на авто",
            "на машину",
        ),
        priority=20,
        auto_send=False,
        text=(
            "Здравствуйте! Да, данный товар подойдет на интересующий вас автомобиль. "
            "С уважением, команда VinylStudio!"
        ),
    ),
)
