from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import current_user
from .db import get_session
from .routers import llm

app = FastAPI(title="Dev Stack API")
app.include_router(llm.router)


@app.get("/health")
async def health(session: AsyncSession = Depends(get_session)):
    await session.execute(text("SELECT 1"))
    return {"status": "ok", "db": "up"}


@app.get("/me")
async def me(user: dict = Depends(current_user)):
    return {"username": user.get("preferred_username"), "email": user.get("email")}
