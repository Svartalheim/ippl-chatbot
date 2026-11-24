"""
Penyamaran PII (Personally Identifiable Information) - NFR-SEC-010.

Dipakai sebelum teks kueri/jawaban ditulis ke log aplikasi atau log audit,
sehingga data pribadi pengguna tidak tersimpan dalam bentuk mentah.
"""
import re
from typing import List, Tuple

# Urutan penting: pola yang lebih spesifik dijalankan lebih dulu.
_PII_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    # NPWP: 99.999.999.9-999.999
    ("NPWP", re.compile(r"\b\d{2}\.\d{3}\.\d{3}\.\d-\d{3}\.\d{3}\b")),
    # NIK (KTP): 16 digit
    ("NIK", re.compile(r"(?<!\d)\d{16}(?!\d)")),
    # Telepon Indonesia: +62 / 62 / 08, 9-13 digit total
    ("TELEPON", re.compile(r"(?<![\w+])(?:\+62|62|0)8\d{1,3}[ -]?\d{3,4}[ -]?\d{3,5}(?!\d)")),
    # Nomor kartu (13-19 digit, boleh dipisah spasi/strip)
    ("NO_KARTU", re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")),
    # Nomor rekening (10-15 digit berurutan)
    ("NO_REKENING", re.compile(r"(?<!\d)\d{10,15}(?!\d)")),
]


def redact_pii(text: str) -> str:
    """Ganti setiap PII yang terdeteksi dengan penanda [LABEL]."""
    if not text:
        return text
    redacted = text
    for label, pattern in _PII_PATTERNS:
        redacted = pattern.sub(f"[{label}]", redacted)
    return redacted


def contains_pii(text: str) -> bool:
    return bool(text) and redact_pii(text) != text
