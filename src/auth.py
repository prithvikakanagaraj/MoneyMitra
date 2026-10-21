"""
MoneyMitra authentication utilities.

Handles secure password hashing and verification.
Passwords are never stored as plain text.
"""

from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)

# Argon2 securely hashes passwords using a unique salt.
_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """
    Hash a password before saving it to the database.

    Returns:
        A secure Argon2 password hash.

    Raises:
        ValueError: If the password is empty or invalid.
    """
    if not isinstance(password, str) or not password:
        raise ValueError("Password cannot be empty.")

    return _password_hasher.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    """
    Check whether a password matches its stored Argon2 hash.

    Returns:
        True if the password matches, otherwise False.
    """
    if not isinstance(password, str) or not isinstance(stored_hash, str):
        return False

    if not password or not stored_hash:
        return False

    try:
        return _password_hasher.verify(stored_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(stored_hash: str) -> bool:
    """
    Check whether a stored password hash should be upgraded
    to the current Argon2 security settings.
    """
    try:
        return _password_hasher.check_needs_rehash(stored_hash)
    except (TypeError, ValueError):
        return True