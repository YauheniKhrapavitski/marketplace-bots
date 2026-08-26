from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Feedback(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    nm_id: int | None = Field(default=None, alias="nmId")
    product_name: str | None = Field(default=None, alias="productName")
    supplier_article: str | None = Field(default=None, alias="supplierArticle")
    buyer_name: str | None = Field(default=None, alias="userName")
    rating: int = 5
    text: str | None = None
    pros: str | None = None
    cons: str | None = None
    created_at: datetime | None = Field(default=None, alias="createdDate")
    raw: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_wb(cls, data: dict[str, Any]) -> "Feedback":
        product = data.get("productDetails") or {}
        payload = {
            "id": data.get("id") or data.get("feedbackId"),
            "nmId": data.get("nmId") or product.get("nmId"),
            "productName": data.get("productName") or product.get("productName"),
            "supplierArticle": data.get("supplierArticle") or product.get("supplierArticle"),
            "userName": data.get("userName") or data.get("buyerName"),
            "rating": data.get("productValuation") or data.get("rating") or 5,
            "text": data.get("text"),
            "pros": data.get("pros"),
            "cons": data.get("cons"),
            "createdDate": data.get("createdDate") or data.get("createdAt"),
            "raw": data,
        }
        return cls.model_validate(payload)
