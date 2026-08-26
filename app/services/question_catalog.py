import csv
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

CATALOG_VERSION = "sheet-2026-07-24"
DEFAULT_CATALOG_PATH = Path("data/wb_product_catalog.csv")


@dataclass(frozen=True)
class ProductCatalogItem:
    seller_sku: str
    brand: str
    model: str
    production_year_range: str
    element: str
    piece_count: str
    comment: str

    @property
    def is_universal(self) -> bool:
        return normalize_text(self.brand) in {"универсальное", "универсални"}


@dataclass(frozen=True)
class YearRange:
    start: int
    end: int
    label: str

    def contains(self, year: int) -> bool:
        return self.start <= year <= self.end


class ProductCatalog:
    def __init__(self, items: list[ProductCatalogItem]) -> None:
        self.items = items
        self.by_sku = {normalize_sku(item.seller_sku): item for item in items}

    @classmethod
    def from_csv(cls, path: Path = DEFAULT_CATALOG_PATH) -> "ProductCatalog":
        rows: list[ProductCatalogItem] = []
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            next(reader, None)
            for row in reader:
                padded = row + [""] * (7 - len(row))
                seller_sku, brand, model, years, element, piece_count, comment = padded[:7]
                if not seller_sku.strip():
                    continue
                rows.append(
                    ProductCatalogItem(
                        seller_sku=seller_sku.strip(),
                        brand=brand.strip(),
                        model=model.strip(),
                        production_year_range=years.strip(),
                        element=element.strip(),
                        piece_count=piece_count.strip(),
                        comment=comment.strip(),
                    )
                )
        return cls(rows)

    def get_by_sku(self, seller_sku: str | None) -> ProductCatalogItem | None:
        if not seller_sku:
            return None
        return self.by_sku.get(normalize_sku(seller_sku))

    def find(
        self,
        *,
        brand: str | None,
        model: str | None,
        element: str | None,
        year: int | None,
        limit: int = 10,
    ) -> list[ProductCatalogItem]:
        ranked: list[tuple[int, ProductCatalogItem]] = []
        brand_norm = normalize_text(brand)
        model_norm = normalize_text(model)
        element_norm = normalize_text(element)
        for item in self.items:
            score = 0
            item_brand = normalize_text(item.brand)
            item_model = normalize_model(item.model)
            item_element = normalize_text(item.element)
            if brand_norm:
                if brand_norm != item_brand and brand_norm not in aliases_for_text(item.brand):
                    continue
                score += 40
            if model_norm:
                if model_norm not in item_model and not any(
                    alias in item_model for alias in aliases_for_text(model_norm)
                ):
                    continue
                score += 40
            if element_norm:
                if not element_matches(element_norm, item_element):
                    continue
                score += 30
            if year is not None and not item.is_universal:
                year_range = select_year_range(item, model)
                if year_range is None:
                    score -= 10
                elif year_range.contains(year):
                    score += 20
                else:
                    score -= 100
            ranked.append((score, item))
        ranked.sort(key=lambda pair: pair[0], reverse=True)
        return [item for score, item in ranked if score > 0][:limit]


@lru_cache
def load_product_catalog(path: str = str(DEFAULT_CATALOG_PATH)) -> ProductCatalog:
    return ProductCatalog.from_csv(Path(path))


def normalize_sku(value: str) -> str:
    return re.sub(r"\s+", "", value.strip().lower())


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    text = value.lower().replace("ё", "е").replace("×", "x").replace("х", "x")
    text = re.sub(r"[^\w%+/-]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def normalize_model(value: str | None) -> str:
    text = normalize_text(value)
    text = re.sub(r"\b(19|20)\d{2}\+?\b", " ", text)
    text = text.replace("+", " ")
    return re.sub(r"\s+", " ", text).strip()


def aliases_for_text(value: str | None) -> set[str]:
    text = normalize_text(value)
    aliases = {text}
    replacements = {
        "лада": "lada",
        "танк": "tank",
        "джили": "geely",
        "белджи": "belgee",
        "шкода": "skoda",
        "черри": "chery",
        "чери": "chery",
        "хавал": "haval",
        "москвич": "москвич",
        "веста": "vesta",
        "гранта": "granta",
        "кулрей": "coolray",
        "тигго": "tiggo",
        "джетур": "jetour",
        "тенет": "tenet",
    }
    for source, target in replacements.items():
        if source in text:
            aliases.add(text.replace(source, target))
        if target in text:
            aliases.add(text.replace(target, source))
    return aliases


def element_matches(requested: str, actual: str) -> bool:
    requested_group = element_group(requested)
    actual_group = element_group(actual)
    return requested_group == actual_group or requested in actual or actual in requested


def element_group(text: str) -> str:
    value = normalize_text(text)
    if any(word in value for word in ("передние фары", "фары", "оптика")):
        return "front_lights"
    if any(word in value for word in ("птф", "противотуман")):
        return "front_lights"
    if any(word in value for word in ("задние фонари", "задние фары")):
        return "rear_lights"
    if "стойки" in value and "лобового" in value:
        return "windshield_pillars"
    if "стойки" in value and any(word in value for word in ("двер", "боков")):
        return "door_pillars"
    if "капот" in value:
        return "hood"
    if "кры" in value:
        return "roof"
    if "порог" in value:
        return "sills"
    if "полка" in value or "задний бампер" in value:
        return "rear_bumper_shelf"
    if "бампер" in value:
        return "bumper"
    if "антиманикюр" in value or "руч" in value:
        return "door_handles"
    if "экран" in value or "монитор" in value:
        return "screen"
    if "универсальная полоска" in value or re.search(r"\d+\s*x\s*\d+", value):
        return "universal_strip"
    return value


def select_year_range(item: ProductCatalogItem, model: str | None = None) -> YearRange | None:
    raw = item.production_year_range.strip()
    if not raw:
        return None
    model_norm = normalize_text(model)
    if ":" in raw:
        for part in raw.split(";"):
            if ":" not in part:
                continue
            label, years = part.split(":", 1)
            if model_norm and normalize_text(label) not in model_norm:
                continue
            parsed = parse_simple_range(years.strip())
            if parsed:
                return YearRange(parsed[0], parsed[1], f"{label.strip()}: {years.strip()}")
        return None
    parsed = parse_simple_range(raw)
    if parsed is None:
        return None
    return YearRange(parsed[0], parsed[1], raw)


def parse_simple_range(value: str) -> tuple[int, int] | None:
    match = re.search(r"(19\d{2}|20\d{2})\s*[-–]\s*(19\d{2}|20\d{2})", value)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))
