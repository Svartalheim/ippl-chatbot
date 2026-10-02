import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..auth import current_user
from ..config import settings

router = APIRouter(prefix="/llm", tags=["llm"])


class ChatIn(BaseModel):
    prompt: str


@router.post("/chat")
async def chat(body: ChatIn, user: dict = Depends(current_user)):
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"{settings.ollama_url}/api/chat",
            json={
                "model": settings.ollama_model,
                "stream": False,
                "messages": [{"role": "user", "content": body.prompt}],
            },
        )
        r.raise_for_status()
    return {"user": user.get("preferred_username"), "answer": r.json()["message"]["content"]}
