from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import current_user, UserInfo
from .db import get_session
from .routers import llm, auth

app = FastAPI(
    title="IPPL Chatbot API",
    description="API untuk chatbot dengan autentikasi Keycloak dan LLM integration",
    version="1.0.0",
)

# Include routers
app.include_router(auth.router)
app.include_router(llm.router)


@app.get("/health", tags=["System"])
async def health(session: AsyncSession = Depends(get_session)):
    """Health check endpoint untuk monitoring"""
    await session.execute(text("SELECT 1"))
    return {"status": "ok", "db": "up"}


@app.get("/me", tags=["User"], summary="Get current user info")
async def me(user: UserInfo = Depends(current_user)):
    """
    Mendapatkan informasi user yang sedang login dari JWT token.
    
    Memerlukan header: `Authorization: Bearer <access_token>`
    """
    return user.to_dict()
