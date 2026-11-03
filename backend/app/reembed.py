"""
Embed ulang chunk yang masih memakai vektor mock (mis. dokumen seed yang dibuat
sebelum model embedding Ollama selesai di-pull).

Jalankan: docker compose exec backend python -m app.reembed   (atau: make reembed)
"""
import asyncio

from .db import SessionLocal
from .services.ingestion_service import ollama_embedding, reembed_stale_chunks


async def main() -> None:
    await ollama_embedding("ping")  # gagal cepat bila model embedding belum siap
    async with SessionLocal() as session:
        count = await reembed_stale_chunks(session)
    print(f"✅ {count} chunk di-embed ulang dengan model Ollama.")


if __name__ == "__main__":
    asyncio.run(main())
