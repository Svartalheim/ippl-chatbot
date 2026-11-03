"""
Kalibrasi ambang relevansi RAG (RAG_SIMILARITY_THRESHOLD).

Menjalankan sekumpulan pertanyaan berlabel terhadap chunk di pgvector (tanpa filter RBAC)
dan menampilkan skor kemiripan teratas. Ambang yang baik berada di antara skor terendah
pertanyaan yang BISA dijawab dan skor tertinggi pertanyaan yang TIDAK bisa dijawab.

Jalankan: docker compose exec backend python -m app.calibrate_rag   (atau: make calibrate)
Tambahkan pertanyaan Anda sendiri ke daftar CASES bila dokumen sudah bertambah.
"""
import asyncio

from sqlalchemy import text

from .config import settings
from .db import SessionLocal
from .services.ingestion_service import embedding_version, ollama_embedding

# (pertanyaan, nama file yang seharusnya menjawab — None bila tidak ada dokumen yang menjawab)
CASES = [
    ("Berapa hari hak cuti tahunan karyawan?", "Peraturan Perusahaan 2026.pdf"),
    ("Bagaimana prosedur pengajuan cuti di portal HR?", "Panduan Portal HR.pdf"),
    ("Berapa total anggaran bonus divisi Finance tahun ini?", "Anggaran Bonus 2026.pdf"),
    ("Bagaimana realisasi anggaran Q3 2026?", "Laporan Keuangan Q3 2026.pdf"),
    ("Apa strategi akuisisi Proyek X?", "Rencana Akuisisi Proyek X.pdf"),
    ("Apa saja tahapan orientasi karyawan baru?", "SOP Onboarding Karyawan.docx"),
    ("Kapan saja hari libur nasional 2026?", "Jadwal Libur Nasional 2026.pdf"),
    ("Berapakah rata-rata gaji karyawan?", None),
    ("Siapa CEO perusahaan saat ini?", None),
    ("Bagaimana cara reset password WiFi kantor?", None),
    ("Apa menu kantin hari ini?", None),
    ("Berapa harga saham perusahaan?", None),
]

SQL = text(
    """
    SELECT d.filename, dc.metadata_json->>'embedding_source' AS src,
           1 - (dc.embedding <=> CAST(:v AS vector)) AS score
    FROM document_chunks dc JOIN documents d ON d.id = dc.document_id
    ORDER BY dc.embedding <=> CAST(:v AS vector) LIMIT 3
    """
)


async def main() -> None:
    answerable, unanswerable, wrong_top = [], [], 0
    async with SessionLocal() as session:
        stale = (await session.execute(
            text("SELECT count(*) FROM document_chunks WHERE metadata_json->>'embedding_source' IS DISTINCT FROM :v"),
            {"v": embedding_version()},
        )).scalar_one()
        if stale:
            print(f"⚠️  {stale} chunk belum memakai embedding {embedding_version()}. Jalankan 'make reembed' dulu.\n")

        for question, expected in CASES:
            vec = await ollama_embedding(question, kind="query")
            rows = (await session.execute(SQL, {"v": "[" + ",".join(map(str, vec)) + "]"})).mappings().all()
            best = float(rows[0]["score"]) if rows else 0.0
            label = "BISA" if expected else "TIDAK"
            print(f"[{label:5}] {best:.3f}  {question}")
            for r in rows:
                mark = "✓" if expected and r["filename"] == expected else " "
                print(f"          {mark} {float(r['score']):.3f}  {r['filename']}")
            if expected:
                answerable.append(best)
                if rows and rows[0]["filename"] != expected:
                    wrong_top += 1
            else:
                unanswerable.append(best)

    print("\n" + "=" * 64)
    print(f"Ambang saat ini (RAG_SIMILARITY_THRESHOLD): {settings.rag_similarity_threshold}")
    lo, hi = min(answerable), max(unanswerable)
    print(f"Skor terbaik terendah — pertanyaan BISA dijawab   : {lo:.3f}")
    print(f"Skor terbaik tertinggi — pertanyaan TIDAK dijawab : {hi:.3f}")
    if lo > hi:
        print(f"✅ Terpisah dengan baik. Saran ambang: {round((lo + hi) / 2, 2)}")
    else:
        print("⚠️  Skor tumpang tindih — ambang saja tidak cukup memisahkan. Andalkan aturan "
              "'tidak ditemukan' pada prompt LLM, atau perbaiki chunk/dokumen seed.")
        print(f"   Kompromi: {round((lo + hi) / 2, 2)} (lebih tinggi = lebih ketat, lebih sedikit sumber palsu)")
    if wrong_top:
        print(f"⚠️  {wrong_top} pertanyaan BISA dijawab mendapat dokumen teratas yang salah.")
    print("Set di .env: RAG_SIMILARITY_THRESHOLD=<nilai>, lalu: docker compose up -d backend")


if __name__ == "__main__":
    asyncio.run(main())
