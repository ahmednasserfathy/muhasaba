import hashlib
import secrets
from collections import OrderedDict
from threading import Lock
from time import monotonic

from fastapi import HTTPException
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

password_hasher = PasswordHash.recommended()
DUMMY_HASH = password_hasher.hash(secrets.token_urlsafe(32))


def verify_password(password: str, encoded: str | None) -> bool:
    try:
        valid = password_hasher.verify(password, encoded or DUMMY_HASH)
    except UnknownHashError:
        password_hasher.verify(password, DUMMY_HASH)
        return False
    return valid and encoded is not None


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_token(prefix: str) -> str:
    return prefix + secrets.token_urlsafe(32)


class RateLimiter:
    """Bounded single-process limiter. Shared edge limits required before scaling."""

    def __init__(self, capacity=4096, clock=monotonic):
        self.capacity = capacity
        self.clock = clock
        self.entries = OrderedDict()
        self.lock = Lock()

    def check(self, key: str, limit: int, window: int):
        now = self.clock()
        with self.lock:
            # Windows may differ, so expire by deadline rather than insertion order.
            for expired in [k for k, (_, end) in self.entries.items() if end <= now]:
                del self.entries[expired]
            count, end = self.entries.get(key, (0, now + window))
            if count >= limit or (
                key not in self.entries and len(self.entries) >= self.capacity
            ):
                raise HTTPException(
                    429,
                    "Too many attempts; try again later",
                    headers={"Retry-After": str(max(1, int(end - now) + 1))},
                )
            self.entries[key] = (count + 1, end)


limiter = RateLimiter()
