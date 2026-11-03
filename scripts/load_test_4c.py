#!/usr/bin/env python3
"""
Aktivitas 4c: Uji Kinerja & Beban (Performance & Load Testing)

Mengirim kueri RAG nyata ke backend FastAPI dengan N pengguna konkuren dan
menghitung persentil p95 latensi end-to-end untuk memverifikasi target
"95% kueri selesai < 5 detik".

Alur yang diuji sama persis dengan frontend:
  1. POST /auth/login             (sekali per akun uji, token Keycloak asli)
  2. POST /chat/sessions          (satu sesi per akun uji)
  3. POST /chat/sessions/{id}/query  (diukur: sanitasi -> embedding -> pgvector RBAC -> Ollama -> audit log)

Tidak ada mode simulasi: bila backend tidak dapat dihubungi, skrip berhenti dengan
exit code 2 agar hasil uji tidak pernah berupa angka palsu.

Contoh:
  python scripts/load_test_4c.py --concurrency 500 --requests 500
  python scripts/load_test_4c.py --concurrency 50 --requests 200 --warmup 5
"""
import argparse
import asyncio
import random
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import httpx

# Akun uji dari infra/keycloak/dev-realm.json beserta pertanyaan yang sesuai perannya.
# Sebagian pertanyaan sengaja lintas-klasifikasi agar jalur QUERY_DENIED ikut terukur.
TEST_ACCOUNTS: List[Tuple[str, str, List[str]]] = [
    ("andi", "password123", [
        "Bagaimana prosedur pengajuan cuti di portal HR?",
        "Kapan saja hari libur nasional tahun 2026?",
        "Apa saja tahapan orientasi karyawan baru?",
    ]),
    ("rina", "password123", [
        "Berapa hari hak cuti tahunan karyawan?",
        "Berapa sisa cuti yang boleh dibawa ke tahun berikutnya?",
        "Berapa total anggaran bonus divisi Finance tahun ini?",
    ]),
    ("dimas", "password123", [
        "Bagaimana realisasi anggaran Q3 2026?",
        "Berapa total anggaran bonus divisi Finance tahun 2026?",
        "Berapa hari hak cuti tahunan karyawan?",
    ]),
    ("sari", "password123", [
        "Apa strategi akuisisi Proyek X?",
        "Bagaimana realisasi anggaran Q3 2026?",
        "Berapa hari hak cuti tahunan karyawan?",
    ]),
]


@dataclass
class Account:
    username: str
    password: str
    questions: List[str]
    access_token: str = ""
    refresh_token: str = ""
    session_id: str = ""
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


@dataclass
class Result:
    ok: bool
    latency: float
    http_status: int
    rag_status: str = ""
    error: str = ""


def percentile(data: List[float], pct: float) -> float:
    """Persentil metode nearest-rank."""
    if not data:
        return 0.0
    ordered = sorted(data)
    rank = max(1, int(round(pct / 100.0 * len(ordered) + 0.4999)))
    return ordered[min(rank, len(ordered)) - 1]


async def login(client: httpx.AsyncClient, base_url: str, acc: Account) -> None:
    r = await client.post(
        f"{base_url}/auth/login",
        json={"username": acc.username, "password": acc.password},
        timeout=20.0,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Login '{acc.username}' gagal (HTTP {r.status_code}): {r.text[:200]}")
    data = r.json()
    acc.access_token = data["access_token"]
    acc.refresh_token = data["refresh_token"]


async def refresh(client: httpx.AsyncClient, base_url: str, acc: Account, stale_token: str) -> None:
    """Perbarui token sekali saja walau banyak worker menerima 401 bersamaan."""
    async with acc.lock:
        if acc.access_token != stale_token:
            return  # sudah diperbarui worker lain
        r = await client.post(
            f"{base_url}/auth/refresh",
            json={"refresh_token": acc.refresh_token},
            timeout=20.0,
        )
        if r.status_code == 200:
            data = r.json()
            acc.access_token = data["access_token"]
            acc.refresh_token = data["refresh_token"]
        else:
            await login(client, base_url, acc)


async def create_session(client: httpx.AsyncClient, base_url: str, acc: Account) -> None:
    r = await client.post(
        f"{base_url}/chat/sessions",
        json={"title": f"Uji beban 4c ({acc.username})"},
        headers={"Authorization": f"Bearer {acc.access_token}"},
        timeout=20.0,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Gagal membuat sesi chat '{acc.username}' (HTTP {r.status_code}): {r.text[:200]}")
    acc.session_id = r.json()["id"]


async def send_query(
    client: httpx.AsyncClient,
    base_url: str,
    acc: Account,
    question: str,
    semaphore: asyncio.Semaphore,
    request_timeout: float,
) -> Result:
    async with semaphore:
        for attempt in range(2):
            token = acc.access_token
            t0 = time.perf_counter()
            try:
                r = await client.post(
                    f"{base_url}/chat/sessions/{acc.session_id}/query",
                    json={"content": question},
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=request_timeout,
                )
            except httpx.TimeoutException:
                return Result(False, time.perf_counter() - t0, 0, error="timeout")
            except httpx.HTTPError as e:
                return Result(False, time.perf_counter() - t0, 0, error=type(e).__name__)
            elapsed = time.perf_counter() - t0

            if r.status_code == 401 and attempt == 0:
                await refresh(client, base_url, acc, token)
                continue  # ulangi sekali dengan token baru (waktu refresh tidak dihitung)

            if r.status_code != 200:
                return Result(False, elapsed, r.status_code, error=r.text[:120])
            body = r.json()
            rag_status = body.get("status", "")
            # ERROR = pipeline gagal (mis. Ollama down) -> bukan respons yang valid
            return Result(rag_status != "ERROR", elapsed, 200, rag_status=rag_status)
        return Result(False, 0.0, 401, error="unauthorized setelah refresh")


async def run_benchmark(
    base_url: str,
    concurrency: int,
    total_requests: int,
    target_p95: float,
    warmup: int,
    request_timeout: float,
    max_error_rate: float,
) -> int:
    print("=" * 72)
    print("  AKTIVITAS 4c: UJI KINERJA & BEBAN RAG CHATBOT")
    print("=" * 72)
    print(f"  Backend            : {base_url}")
    print(f"  Pengguna konkuren  : {concurrency}")
    print(f"  Total kueri        : {total_requests} (+{warmup} warm-up, tidak dihitung)")
    print(f"  Target p95         : < {target_p95} detik")
    print(f"  Timeout per kueri  : {request_timeout} detik")
    print("-" * 72)

    limits = httpx.Limits(max_connections=concurrency + 20, max_keepalive_connections=concurrency)
    async with httpx.AsyncClient(limits=limits) as client:
        # 0. Backend harus hidup — tidak ada fallback simulasi
        try:
            h = await client.get(f"{base_url}/health", timeout=5.0)
            h.raise_for_status()
        except Exception as e:
            print(f"[ERROR] Backend tidak dapat dihubungi di {base_url}/health: {e}")
            print("        Jalankan 'make up' terlebih dahulu. Uji dibatalkan (tanpa angka simulasi).")
            return 2

        # 1. Login & buat sesi untuk setiap akun uji
        accounts = [Account(u, p, q) for u, p, q in TEST_ACCOUNTS]
        try:
            for acc in accounts:
                await login(client, base_url, acc)
                await create_session(client, base_url, acc)
        except Exception as e:
            print(f"[ERROR] Persiapan akun uji gagal: {e}")
            return 2
        print(f"  Login & sesi chat siap untuk: {', '.join(a.username for a in accounts)}")

        # 2. Warm-up (memuat model Ollama ke memori agar cold start tidak merusak p95)
        if warmup:
            print(f"  Warm-up {warmup} kueri...")
            sem1 = asyncio.Semaphore(1)
            for i in range(warmup):
                acc = accounts[i % len(accounts)]
                await send_query(client, base_url, acc, acc.questions[0], sem1, request_timeout)

        # 3. Uji beban
        rng = random.Random(42)
        semaphore = asyncio.Semaphore(concurrency)
        tasks = []
        for i in range(total_requests):
            acc = accounts[i % len(accounts)]
            tasks.append(send_query(client, base_url, acc, rng.choice(acc.questions), semaphore, request_timeout))

        print("  Menjalankan uji beban...")
        t_start = time.perf_counter()
        results: List[Result] = await asyncio.gather(*tasks)
        wall = time.perf_counter() - t_start

    # 4. Metrik
    ok = [r for r in results if r.ok]
    failed = [r for r in results if not r.ok]
    # p95 dihitung atas SEMUA kueri (termasuk yang gagal/timeout, dengan latensi aktualnya)
    # agar kegagalan tidak membuat p95 terlihat lebih baik.
    all_lat = [r.latency for r in results]
    ok_lat = [r.latency for r in ok]
    error_rate = len(failed) / len(results) if results else 1.0

    print("\n" + "=" * 72)
    print("  HASIL")
    print("=" * 72)
    print(f"  Durasi total            : {wall:.2f} s  ({len(results) / wall:.1f} kueri/detik)")
    print(f"  Berhasil / gagal        : {len(ok)} / {len(failed)}  (error rate {error_rate:.1%})")
    rag_counts = Counter(r.rag_status for r in ok)
    print(f"  Status RAG              : {dict(rag_counts)}")
    if failed:
        fail_counts: Dict[str, int] = Counter(
            (r.error if r.http_status == 0 else f"HTTP {r.http_status}") for r in failed
        )
        print(f"  Jenis kegagalan         : {dict(fail_counts)}")
    print("-" * 72)
    print("  Latensi semua kueri (detik):")
    print(f"    min {min(all_lat):.3f} | p50 {percentile(all_lat, 50):.3f} | p90 {percentile(all_lat, 90):.3f} "
          f"| p95 {percentile(all_lat, 95):.3f} | p99 {percentile(all_lat, 99):.3f} | max {max(all_lat):.3f}")
    if ok_lat:
        print(f"  p95 kueri berhasil saja : {percentile(ok_lat, 95):.3f} s")
    print("=" * 72)

    p95 = percentile(all_lat, 95)
    passed = p95 < target_p95 and error_rate <= max_error_rate
    if passed:
        print(f"\n[LULUS] p95 {p95:.3f}s < {target_p95}s dan error rate {error_rate:.1%} <= {max_error_rate:.0%} "
              f"pada {concurrency} pengguna konkuren.")
        return 0
    reasons = []
    if p95 >= target_p95:
        reasons.append(f"p95 {p95:.3f}s >= {target_p95}s")
    if error_rate > max_error_rate:
        reasons.append(f"error rate {error_rate:.1%} > {max_error_rate:.0%}")
    print(f"\n[GAGAL] {'; '.join(reasons)}.")
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Uji beban RAG chatbot (Aktivitas 4c)")
    parser.add_argument("--base-url", default="http://localhost:8000", help="URL backend FastAPI")
    parser.add_argument("--concurrency", type=int, default=500, help="Jumlah pengguna konkuren (default 500)")
    parser.add_argument("--requests", type=int, default=500, help="Total kueri yang diukur (default 500)")
    parser.add_argument("--target-p95", type=float, default=5.0, help="Batas p95 dalam detik (default 5.0)")
    parser.add_argument("--warmup", type=int, default=3, help="Jumlah kueri pemanasan yang tidak dihitung")
    parser.add_argument("--timeout", type=float, default=60.0, help="Timeout per kueri dalam detik")
    parser.add_argument("--max-error-rate", type=float, default=0.01, help="Batas error rate (default 0.01 = 1%%)")
    args = parser.parse_args()

    sys.exit(asyncio.run(run_benchmark(
        base_url=args.base_url.rstrip("/"),
        concurrency=args.concurrency,
        total_requests=args.requests,
        target_p95=args.target_p95,
        warmup=args.warmup,
        request_timeout=args.timeout,
        max_error_rate=args.max_error_rate,
    )))


if __name__ == "__main__":
    main()
