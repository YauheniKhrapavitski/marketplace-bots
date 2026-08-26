from app.services.ozon_review_template_catalog import STARTER_OZON_REVIEW_TEMPLATES
from app.services.template_catalog import STARTER_TEMPLATES


def test_ozon_catalog_mirrors_wb_review_templates() -> None:
    codes = {template.code for template in STARTER_OZON_REVIEW_TEMPLATES}
    active_codes = {
        template.code for template in STARTER_OZON_REVIEW_TEMPLATES if template.is_active
    }

    assert len(STARTER_OZON_REVIEW_TEMPLATES) == 14
    assert {f"ozon_{template.code}" for template in STARTER_TEMPLATES}.issubset(codes)
    assert len(active_codes) == len(STARTER_TEMPLATES)
    assert "ozon_rating_5_positive" in active_codes
    assert "ozon_item_damage" not in active_codes
