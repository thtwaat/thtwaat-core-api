"""
scripts/break_glass_reset_password.py

ONE-TIME, TIGHTLY SCOPED break-glass password reset for a single, known
THTWAAT platform admin recovery incident. This is not a general-purpose
admin tool — it hardcodes the exact target identity below and refuses to
touch any other row.

Target (verified by exact UUID, not by email lookup):
    id           = 85dbce0c-861b-4fee-bd1a-0a4efd7f6721
    email        = thtwaat@gmail.com
    company slug = tts
    role         = super_admin

Why this exists: the normal recovery path is POST /api/v1/auth/forgot-password
+ POST /api/v1/auth/reset-password (see app/auth/service.py). This script is
ONLY for the case where that path cannot be used (e.g. email delivery isn't
configured) and there is no other way to obtain a platform-admin session.

Safety properties:
  - No HTTP endpoint, no router change, no change to any existing API.
  - Targets the user by exact UUID, never by email lookup. Before writing
    anything, it re-reads that row and aborts if its email, company slug, or
    role don't match the expected values above.
  - Requires a one-time BREAK_GLASS_TOKEN (plus its expected SHA-256 hash)
    supplied via environment variables set only in the operator's shell for
    this invocation — never written to a file, never committed, never put
    in .env.prod. Compared with secrets.compare_digest().
  - Requires typing an exact confirmation phrase interactively, after
    identity verification and before any write.
  - Reads the new password interactively with getpass, twice, and never
    prints/logs/stores it (or the invite/temp/existing hash) anywhere.
  - Reuses AuthService.get_password_hash() — the exact bcrypt call the real
    reset-password endpoint uses — and revokes only this user's own
    RefreshToken rows, mirroring AuthService.reset_password()'s behavior.
  - Writes an explicit, distinctly-tagged audit event via the existing
    app.auth.audit.log_otp_event() helper.
  - Touches exactly one user row. Never creates, deletes, or modifies any
    company, and never touches any other user.

One-time token setup (run once, in the operator's shell, right before use —
do not save either value to a file):

    export BREAK_GLASS_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
    export BREAK_GLASS_TOKEN_SHA256="$(python -c 'import os,hashlib; print(hashlib.sha256(os.environ["BREAK_GLASS_TOKEN"].encode()).hexdigest())')"

Usage:

    python scripts/break_glass_reset_password.py

The script then verifies the target row, asks for the exact confirmation
phrase, then asks for the new password twice via getpass.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import sys
import uuid
from typing import Callable, Optional

import getpass

from app.rbac.enums import EnterpriseRole

EXPECTED_USER_ID = uuid.UUID("85dbce0c-861b-4fee-bd1a-0a4efd7f6721")
EXPECTED_EMAIL = "thtwaat@gmail.com"
EXPECTED_COMPANY_SLUG = "tts"
EXPECTED_ROLE = EnterpriseRole.SUPER_ADMIN

ENV_BREAK_GLASS_TOKEN = "BREAK_GLASS_TOKEN"
ENV_BREAK_GLASS_TOKEN_SHA256 = "BREAK_GLASS_TOKEN_SHA256"

# Typed verbatim and interactively (never via env/CLI) before any write.
CONFIRMATION_PHRASE = "BREAK GLASS RESET THTWAAT PLATFORM ADMIN"

AUDIT_EVENT = "PASSWORD_RESET_BREAK_GLASS_CLI"


class BreakGlassError(RuntimeError):
    """Raised for any pre-flight verification failure. Never raised after a write."""


def verify_break_glass_token(supplied: Optional[str], expected_sha256: Optional[str]) -> bool:
    """Constant-time check that sha256(supplied) == expected_sha256.

    Fails closed (returns False) if either value is missing/empty — a token
    with no configured expected hash is never treated as "no check needed".
    """
    if not supplied or not expected_sha256:
        return False
    actual = hashlib.sha256(supplied.encode("utf-8")).hexdigest()
    return secrets.compare_digest(actual, expected_sha256.strip().lower())


def load_and_verify_target(db) -> "User":  # noqa: F821 - User imported lazily below
    """Fetch the exact target user by UUID and verify identity before any write.

    Never looks the user up by email. Aborts with BreakGlassError (no write
    has happened) if the row doesn't match every expected field.
    """
    from app.companies.model import Company
    from app.users.model import User

    user = db.get(User, EXPECTED_USER_ID)
    if user is None:
        raise BreakGlassError(f"No user found with id={EXPECTED_USER_ID}. Aborting before any write.")

    if user.email != EXPECTED_EMAIL:
        raise BreakGlassError(
            f"Refusing to proceed: user {EXPECTED_USER_ID} has email "
            f"{user.email!r}, expected {EXPECTED_EMAIL!r}. Aborting before any write."
        )

    company = db.get(Company, user.company_id)
    company_slug = getattr(company, "slug", None)
    if company_slug != EXPECTED_COMPANY_SLUG:
        raise BreakGlassError(
            f"Refusing to proceed: user {EXPECTED_USER_ID} belongs to company "
            f"slug {company_slug!r}, expected {EXPECTED_COMPANY_SLUG!r}. Aborting before any write."
        )

    if user.role != EXPECTED_ROLE:
        role_value = getattr(user.role, "value", user.role)
        raise BreakGlassError(
            f"Refusing to proceed: user {EXPECTED_USER_ID} has role {role_value!r}, "
            f"expected {EXPECTED_ROLE.value!r}. Aborting before any write."
        )

    return user


def confirm_execution(reader: Callable[[str], str] = input) -> bool:
    """Require the operator to type the exact phrase to unlock the write.

    Always interactive — takes no value from an environment variable or a
    CLI argument. Returns True only on an exact (case-sensitive) match.
    """
    print(
        "\nYou are about to perform a BREAK-GLASS password reset for the "
        f"THTWAAT platform admin account ({EXPECTED_EMAIL}, company "
        f"'{EXPECTED_COMPANY_SLUG}').\n"
        f"Type this exact phrase to continue: {CONFIRMATION_PHRASE}"
    )
    typed = reader("> ")
    return typed == CONFIRMATION_PHRASE


def read_new_password(
    prompt: str = "New password for the break-glass target: ",
    confirm_prompt: str = "Confirm new password: ",
    reader=getpass.getpass,
) -> str:
    """Interactively read + confirm a new password. Never echoed, never printed."""
    while True:
        pw1 = reader(prompt)
        pw2 = reader(confirm_prompt)
        if pw1 != pw2:
            print("Passwords do not match. Try again.")
            continue
        if len(pw1) < 8:
            print("Password must be at least 8 characters. Try again.")
            continue
        return pw1


def perform_break_glass_reset(db, user: "User", new_password: str) -> None:  # noqa: F821
    """Set the new password via the app's own bcrypt hashing and revoke only
    this user's refresh tokens — mirrors AuthService.reset_password()'s
    mutation, scoped to a single already-verified user row.
    """
    from sqlalchemy import delete

    from app.auth.audit import log_otp_event
    from app.auth.model import RefreshToken
    from app.auth.service import AuthService

    user.hashed_password = AuthService.get_password_hash(new_password)
    db.add(user)
    db.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
    db.commit()

    log_otp_event(
        AUDIT_EVENT,
        email=user.email,
        user_id=user.id,
        company_id=user.company_id,
    )


def main() -> int:
    supplied_token = os.environ.get(ENV_BREAK_GLASS_TOKEN)
    expected_hash = os.environ.get(ENV_BREAK_GLASS_TOKEN_SHA256)
    if not verify_break_glass_token(supplied_token, expected_hash):
        print(
            f"ERROR: {ENV_BREAK_GLASS_TOKEN} is missing or does not match "
            f"{ENV_BREAK_GLASS_TOKEN_SHA256}. Aborting before any check or write."
        )
        return 1

    # Bootstrap ORM mappers before opening a Session outside of main.py —
    # same requirement as scripts/seed_billing_plans.py and friends.
    from app.database.orm_bootstrap import register_orm_models

    register_orm_models()

    from app.database.database import SessionLocal

    db = SessionLocal()
    try:
        try:
            user = load_and_verify_target(db)
        except BreakGlassError as exc:
            print(f"ERROR: {exc}")
            return 1

        role_value = getattr(user.role, "value", user.role)
        print(
            f"Verified target: id={user.id} email={user.email} "
            f"company_slug={EXPECTED_COMPANY_SLUG} role={role_value}"
        )

        if not confirm_execution():
            print("Confirmation phrase did not match. Aborting before any write.")
            return 1

        new_password = read_new_password()
        perform_break_glass_reset(db, user, new_password)
        new_password = None  # best-effort scrub of the local reference
        print(
            "Break-glass password reset complete. All existing refresh tokens "
            "for this user were revoked."
        )
        print("Log in normally via POST /api/v1/auth/login to obtain a fresh session.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
