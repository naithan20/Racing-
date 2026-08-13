"""Unique id generation matching the style of Prisma's cuid() ids closely
enough to be indistinguishable in the UI (lowercase alphanumeric), without
depending on a JS runtime. Format is not the literal cuid2 algorithm — just
a sufficiently-random, sortable-ish, collision-safe string.
"""

from __future__ import annotations

import secrets
import time


def new_id(prefix: str = "") -> str:
    timestamp_part = _base36(int(time.time() * 1000))
    random_part = secrets.token_hex(10)  # 20 hex chars, ~80 bits of entropy
    body = f"{timestamp_part}{random_part}"
    return f"{prefix}{body}" if prefix else body


def _base36(value: int) -> str:
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    if value == 0:
        return "0"
    out = []
    while value:
        value, rem = divmod(value, 36)
        out.append(digits[rem])
    return "".join(reversed(out))
