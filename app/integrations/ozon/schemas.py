from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OzonReview(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    sku: int | None = None
    product_id: int | None = Field(default=None, alias="productId")
    offer_id: str | None = Field(default=None, alias="offerId")
    product_name: str | None = Field(default=None, alias="productName")
    buyer_name: str | None = Field(default=None, alias="buyerName")
    rating: int = 5
    text: str | None = None
    pros: str | None = None
    cons: str | None = None
    published_at: datetime | None = Field(default=None, alias="publishedAt")
    status: str | None = None
    has_official_comment: bool = Field(default=False, alias="hasOfficialComment")
    raw: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_ozon(cls, data: dict[str, Any]) -> "OzonReview":
        product = data.get("product") or {}
        comments = data.get("comments") or []
        payload = {
            "id": data.get("id") or data.get("review_id") or data.get("reviewId"),
            "sku": data.get("sku") or product.get("sku"),
            "productId": data.get("product_id") or data.get("productId") or product.get("id"),
            "offerId": data.get("offer_id") or data.get("offerId") or product.get("offer_id"),
            "productName": (
                data.get("product_name") or data.get("productName") or product.get("name")
            ),
            "buyerName": data.get("buyer_name") or data.get("buyerName") or data.get("author"),
            "rating": data.get("rating") or data.get("score") or 5,
            "text": data.get("text") or data.get("review_text") or data.get("reviewText"),
            "pros": data.get("pros") or data.get("advantages"),
            "cons": data.get("cons") or data.get("disadvantages"),
            "publishedAt": (
                data.get("published_at")
                or data.get("publishedAt")
                or data.get("created_at")
                or data.get("createdAt")
            ),
            "status": data.get("status"),
            "hasOfficialComment": _has_official_comment(data, comments),
            "raw": data,
        }
        return cls.model_validate(payload)


def _has_official_comment(data: dict[str, Any], comments: object) -> bool:
    if data.get("has_official_comment") or data.get("hasOfficialComment"):
        return True
    if data.get("is_commented") or data.get("isCommented"):
        return True
    if isinstance(comments, list):
        return any(isinstance(item, dict) and item.get("is_official") for item in comments)
    return False
