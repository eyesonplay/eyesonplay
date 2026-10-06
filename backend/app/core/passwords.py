"""Password hashing with Argon2id (argon2-cffi defaults follow RFC 9106)."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

MIN_PASSWORD_LENGTH = 10
_hasher = PasswordHasher()
# Compared against when the email is unknown, so a login takes the same time
# whether or not the account exists.
_DUMMY_HASH = _hasher.hash("eyesonplay-timing-equaliser")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def burn_verification(password: str) -> None:
    """Spend the time of a real verification without an account."""
    verify_password(_DUMMY_HASH, password)
