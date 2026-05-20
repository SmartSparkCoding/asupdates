import base64
import hashlib
from typing import Iterable

from cryptography.fernet import Fernet, InvalidToken

from config import EMAIL_ENCRYPTION_KEY, SECRET_KEY

EMAIL_PREFIX = "enc:"


def _derive_key(raw_key: str) -> bytes:
    if raw_key:
        candidate = raw_key.encode("utf-8")
        if len(candidate) == 44:
            return candidate
        return base64.urlsafe_b64encode(hashlib.sha256(candidate).digest())

    return base64.urlsafe_b64encode(hashlib.sha256(SECRET_KEY.encode("utf-8")).digest())


_FERNET = Fernet(_derive_key(EMAIL_ENCRYPTION_KEY))


def normalize_email(email: str) -> str:
    return str(email or "").strip().lower()


def email_lookup_value(email: str) -> str:
    normalized = normalize_email(email)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest() if normalized else ""


def encrypt_email(email: str) -> str:
    normalized = normalize_email(email)
    if not normalized:
        return ""
    token = _FERNET.encrypt(normalized.encode("utf-8")).decode("utf-8")
    return f"{EMAIL_PREFIX}{token}"


def is_encrypted_email(value: str) -> bool:
    return isinstance(value, str) and value.startswith(EMAIL_PREFIX)


def decrypt_email(value: str) -> str:
    if not value:
        return ""

    if not is_encrypted_email(value):
        return normalize_email(value)

    token = value[len(EMAIL_PREFIX) :]
    try:
        return normalize_email(_FERNET.decrypt(token.encode("utf-8")).decode("utf-8"))
    except (InvalidToken, ValueError, TypeError):
        return ""


def migrate_user_emails(conn) -> int:
    """Encrypt plaintext emails in place and populate lookup hashes."""

    cursor = conn.cursor()
    cursor.execute("SELECT id, email, email_lookup FROM users")
    rows = cursor.fetchall()
    updated = 0

    for row in rows:
        user_id = row[0]
        raw_email = row[1] or ""
        current_lookup = row[2] or ""
        decrypted = decrypt_email(raw_email)

        if decrypted:
            normalized = decrypted
            encrypted = encrypt_email(normalized)
        else:
            normalized = normalize_email(raw_email)
            if not normalized:
                continue
            encrypted = encrypt_email(normalized)

        lookup = email_lookup_value(normalized)
        if encrypted != raw_email or lookup != current_lookup:
            cursor.execute(
                "UPDATE users SET email=?, email_lookup=? WHERE id=?",
                (encrypted, lookup, user_id),
            )
            updated += 1

    if updated:
        conn.commit()

    return updated
