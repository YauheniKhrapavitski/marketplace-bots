import httpx

from app.integrations.wildberries.client import WildberriesClient
from app.integrations.wildberries.question_schemas import Question


class WildberriesQuestionsClient(WildberriesClient):
    _rate_limit_cooldown_until = 0.0

    async def get_unanswered_questions(
        self,
        take: int,
        skip: int,
        order: str = "dateDesc",
    ) -> list[Question]:
        response = await self._request(
            "GET",
            "/api/v1/questions",
            params={"isAnswered": "false", "take": take, "skip": skip, "order": order},
        )
        payload = response.json()
        raw_items = payload.get("data", {}).get("questions", payload.get("questions", []))
        return [Question.from_wb(item) for item in raw_items]

    async def send_question_answer(self, question_id: str, text: str) -> None:
        await self._request(
            "PATCH",
            "/api/v1/questions",
            json={"id": question_id, "answer": {"text": text}, "state": "wbRu"},
        )

    async def mark_question_viewed(self, question_id: str) -> httpx.Response:
        return await self._request(
            "PATCH", "/api/v1/questions", json={"id": question_id, "wasViewed": True}
        )
