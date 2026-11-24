"""
Job retensi log audit (NFR-SEC-018).

Menjalankan: docker compose exec backend python -m app.audit_retention [--dry-run]

1. Mengekspor baris audit_logs yang lebih tua dari AUDIT_RETENTION_DAYS ke file
   JSON Lines di AUDIT_ARCHIVE_DIR, beserta SHA-256 file arsip.
2. Mencatat entri AUDIT_ARCHIVE (berisi hash baris terakhir yang diarsipkan = jangkar
   rantai baru) SEBELUM penghapusan, sehingga verify_audit_chain tetap bisa memverifikasi.
3. Menghapus baris tersebut dalam transaksi yang men-set app.audit_retention_days;
   trigger append-only hanya mengizinkan DELETE pada kondisi ini.
"""
import argparse
import asyncio
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select, text

from .config import settings
from .db import SessionLocal
from .models import AuditLog
from .services.audit_service import record_audit_log


async def run_retention(dry_run: bool = False) -> dict:
    days = settings.audit_retention_days
    if days < 30:
        raise ValueError("AUDIT_RETENTION_DAYS minimal 30 hari.")
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(AuditLog).where(AuditLog.created_at < cutoff).order_by(AuditLog.id.asc())
            )
        ).scalars().all()
        if not rows:
            return {"archived": 0, "cutoff": cutoff.isoformat()}

        last = rows[-1]
        archive_dir = Path(settings.audit_archive_dir)
        archive_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        archive_path = archive_dir / f"audit_logs_until_{last.id}_{stamp}.jsonl"

        lines = [
            json.dumps(
                {
                    "id": r.id,
                    "created_at": r.created_at.isoformat(),
                    "actor_user_id": str(r.actor_user_id) if r.actor_user_id else None,
                    "actor_name": r.actor_name,
                    "actor_role": r.actor_role,
                    "ip_address": r.ip_address,
                    "action": r.action,
                    "detail": r.detail,
                    "status": r.status,
                    "prev_hash": r.prev_hash,
                    "curr_hash": r.curr_hash,
                },
                ensure_ascii=False,
            )
            for r in rows
        ]
        content = ("\n".join(lines) + "\n").encode("utf-8")
        file_hash = hashlib.sha256(content).hexdigest()

        result = {
            "archived": len(rows),
            "cutoff": cutoff.isoformat(),
            "archive_file": str(archive_path),
            "archive_sha256": file_hash,
            "anchor_hash": last.curr_hash,
        }
        if dry_run:
            return {**result, "dry_run": True}

        archive_path.write_bytes(content)
        Path(str(archive_path) + ".sha256").write_text(f"{file_hash}  {archive_path.name}\n")

        await record_audit_log(
            session=session,
            actor_name="Sistem",
            actor_role="System",
            action="AUDIT_ARCHIVE",
            detail=(
                f"{len(rows)} entri (id {rows[0].id}-{last.id}) diarsipkan ke {archive_path.name} "
                f"sha256={file_hash}; jangkar rantai={last.curr_hash}"
            ),
            status="Berhasil",
        )

        await session.execute(text(f"SET LOCAL app.audit_retention_days = '{int(days)}'"))
        await session.execute(
            text("DELETE FROM audit_logs WHERE id <= :last_id AND created_at < :cutoff"),
            {"last_id": last.id, "cutoff": cutoff},
        )
        await session.commit()
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Arsipkan & purge log audit melewati periode retensi.")
    parser.add_argument("--dry-run", action="store_true", help="Tampilkan rencana tanpa mengubah data")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run_retention(dry_run=args.dry_run)), indent=2))


if __name__ == "__main__":
    main()
