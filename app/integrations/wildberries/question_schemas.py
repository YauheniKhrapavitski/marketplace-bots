from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Question(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    nm_id: int | None = Field(default=None, alias="nmId")
    imt_id: int | None = Field(default=None, alias="imtId")
    product_name: str | None = Field(default=None, alias="productName")
    supplier_article: str | None = Field(default=None, alias="supplierArticle")
    brand_name: str | None = Field(default=None, alias="brandName")
    text: str
    state: str | None = None
    created_at: datetime | None = Field(default=None, alias="createdDate")
    was_viewed: bool = Field(default=False, alias="wasViewed")
    is_warned: bool = Field(default=False, alias="isWarned")
    raw: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_wb(cls, data: dict[str, Any]) -> "Question":
        product = data.get("productDetails") or {}
        payload = {
            "id": data.get("id"),
            "nmId": data.get("nmId") or product.get("nmId"),
            "imtId": data.get("imtId") or product.get("imtId"),
            "productName": data.get("productName") or product.get("productName"),
            "supplierArticle": data.get("supplierArticle") or product.get("supplierArticle"),
            "brandName": data.get("brandName") or product.get("brandName"),
            "text": data.get("text") or "",
            "state": data.get("state"),
            "createdDate": data.get("createdDate") or data.get("createdAt"),
            "wasViewed": data.get("wasViewed") or False,
            "isWarned": data.get("isWarned") or False,
            "raw": data,
        }
        return cls.model_validate(payload)
