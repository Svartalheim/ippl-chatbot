import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..auth import current_user, UserInfo
from ..config import settings

router = APIRouter(prefix="/llm", tags=["LLM"])


class ChatIn(BaseModel):
    prompt: str


@router.post("/chat", summary="Chat dengan LLM")
async def chat(body: ChatIn, user: UserInfo = Depends(current_user)):
    """
    Kirim prompt ke LLM dan dapatkan response.
    
    Memerlukan autentikasi JWT token.
    """
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
    return {
        "user": user.username,
        "answer": r.json()["message"]["content"]
    }
