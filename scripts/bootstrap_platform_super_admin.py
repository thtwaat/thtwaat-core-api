"""
scripts/bootstrap_platform_super_admin.py

ONE-TIME, TIGHTLY SCOPED bootstrap CLI for the dedicated THTWAAT platform
Super Admin account. This exists for exactly one situation: there is no
existing platform-admin JWT available, so the HTTP-based
scripts/local_provision_super_admin.py cannot be used. This script talks
directly to the database instead (same style as
scripts/break_glass_reset_password.py) and is not a general-purpose admin
tool: it hardcodes the exact target identity below and refuses to touch any
other row.

Target (exact match required, never created/reused by fuzzy lookup):
    company name = THTWAAT Platform
    company slug = thtwaat-platform
    email        = superadmin@thtwaat.com
    role         = EnterpriseRole.SUPER_ADMIN

Safety properties:
  - No HTTP endpoint, no router change, no change to any existing API or
    app/ module.
  - Read-only preflight before any mutation: looks up the company by slug
    and the user by (company_id, email). If a company already exists at
    that slug with a different name, or a user already exists at that email
    with a different role, the script aborts before touching anything.
  - Requires a one-time BOOTSTRAP_SUPER_ADMIN_TOKEN (plus its expected
    SHA-256 hash) supplied via environment variables set only in the
    operator's shell for this invocation — never written to a file, never
    committed. Compared with secrets.compare_digest(), fails closed if
    either value is missing.
  - Requires typing an exact confirmation phrase interactively, after
    preflight and before any write.
  - Never overwrites an existing user's password. If the target user
    already exists, its password is left untouched unless the operator
    BOTH passes --reset-existing-password AND types a second, separate
    confirmation phrase. Only then are refresh tokens for that user
    revoked (mirrors break_glass_reset_password.py's reset behavior).
  - Reads the new password interactively with getpass, twice, and never
    prints/logs/stores it (or any password hash) anywhere. The password is
    never accepted via a CLI argument or environment variable.
  - Reuses AuthService.get_password_hash() — the exact bcrypt call the rest
    of the app uses — for any password it sets.
  - A newly created user is always UserStatus.ACTIVE / is_active=True with
    role=EnterpriseRole.SUPER_ADMIN; there is no code path that creates it
    with any other role.
  - Writes a single, distinctly-tagged audit event
    (PLATFORM_SUPER_ADMIN_BOOTSTRAP_CLI) via the existing
    app.auth.audit.log_otp_event() helper.
  - Exactly one commit for the whole run, and only when there is an actual
    mutation to make; a run where the company and user already exist
    correctly and no reset was requested performs no write at all.

This script does not perform any host/environment detection of its own — it
operates directly against whatever database SessionLocal is configured for
in the current process's environment (same limitation as
break_glass_reset_password.py). The operator is responsible for ensuring
that environment is not production before running it.

One-time token setup (run once, in the operator's shell, right before use —
do not save either value to a file):

    export BOOTSTRAP_SUPER_ADMIN_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
    export BOOTSTRAP_SUPER_ADMIN_TOKEN_SHA256="$(python -c 'import os,hashlib; print(hashlib.sha256(os.environ["BOOTSTRAP_SUPER_ADMIN_TOKEN"].encode()).hexdigest())')"

Usage (create/reuse only, never touches an existing password):

    python scripts/bootstrap_platform_super_admin.py

Usage (also reset the existing user's password, if one already exists):

    python scripts/bootstrap_platform_super_admin.py --reset-existing-password

The script prints the target identity and the exact planned mutation,
then asks for the primary confirmation phrase, then (only if resetting an
existing password) a second confirmation phrase, then the new password
twice via getpass.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import os
import secrets
import sys
import uuid
from dataclasses import dataclass
from typing import Callable, Optional

from app.rbac.enums import EnterpriseRole

TARGET_COMPANY_NAME = "THTWAAT Platform"
TARGET_COMPANY_SLUG = "thtwaat-platform"
TARGET_EMAIL = "superadmin@thtwaat.com"
TARGET_ROLE = EnterpriseRole.SUPER_ADMIN
TARGET_FIRST_NAME = "THTWAAT"
TARGET_LAST_NAME = "Admin"

ENV_BOOTSTRAP_TOKEN = "BOOTSTRAP_SUPER_ADMIN_TOKEN"
ENV_BOOTSTRAP_TOKEN_SHA256 = "BOOTSTRAP_SUPER_ADMIN_TOKEN_SHA256"

# Typed verbatim and interactively (never via env/CLI) before any write.
CONFIRMATION_PHRASE = "BOOTSTRAP THTWAAT PLATFORM SUPER ADMIN"

# Typed verbatim and interactively (never via env/CLI) before overwriting an
# *existing* user's password. Deliberately separate from CONFIRMATION_PHRASE
# so the "create/reuse" path and the "reset an existing password" path each
# require their own explicit operator intent.
RESET_CONFIRMATION_PHRASE = "OVERWRITE EXISTING SUPER ADMIN PASSWORD"

AUDIT_EVENT = "PLATFORM_SUPER_ADMIN_BOOTSTRAP_CLI"


class BootstrapError(RuntimeError):
    """Raised for any pre-flight safety failure. Never raised after a write."""


@dataclass
class BootstrapPlan:
    """Read-only snapshot of what a run would do, computed before any write."""

    company: Optional[object]  # app.companies.model.Company, or None if to be created
    user: Optional[object]  # app.users.model.User, or None if to be created
    create_company: bool
    create_user: bool
    existing_password_set: bool  # True iff the target user already exists


def verify_bootstrap_token(supplied: Optional[str], expected_sha256: Optional[str]) -> bool:
    """Constant-time check that sha256(supplied) == expected_sha256.

    Fails closed (returns False) if either value is missing/empty — a token
    with no configured expected hash is never treated as "no check needed".
    """
    if not supplied or not expected_sha256:
        return False
    actual = hashlib.sha256(supplied.encode("utf-8")).hexdigest()
    return secrets.compare_digest(actual, expected_sha256.strip().lower())


def build_company_lookup_stmt(slug: str):
    """Exact-slug SELECT for the target company. Never a fuzzy/name lookup."""
    from sqlalchemy import select

    from app.companies.model import Company

    return select(Company).where(Company.slug == slug)


def build_user_lookup_stmt(company_id, email: str):
    """Exact (company_id, email) SELECT for the target user. Never global-by-email."""
    from sqlalchemy import select

    from app.users.model import User

    return select(User).where(User.company_id == company_id, User.email == email)


def find_company_by_slug(db, slug: str):
    return db.execute(build_company_lookup_stmt(slug)).scalar_one_or_none()


def find_user_by_email(db, company_id, email: str):
    return db.execute(build_user_lookup_stmt(company_id, email)).scalar_one_or_none()


def build_plan(db) -> BootstrapPlan:
    """Read-only preflight. Aborts with BootstrapError before any write if an
    existing row at the target slug/email doesn't exactly match what's
    expected — never silently repurposes a different company or user."""
    company = find_company_by_slug(db, TARGET_COMPANY_SLUG)
    if company is not None and company.name != TARGET_COMPANY_NAME:
        raise BootstrapError(
            f"Refusing to proceed: company slug {TARGET_COMPANY_SLUG!r} already "
            f"exists with name {company.name!r}, expected {TARGET_COMPANY_NAME!r}. "
            "Aborting before any write."
        )

    user = None
    if company is not None:
        user = find_user_by_email(db, company.id, TARGET_EMAIL)
        if user is not None and user.role != TARGET_ROLE:
            role_value = getattr(user.role, "value", user.role)
            raise BootstrapError(
                f"Refusing to proceed: user {TARGET_EMAIL!r} already exists with "
                f"role {role_value!r}, expected {TARGET_ROLE.value!r}. Aborting "
                "before any write."
            )

    return BootstrapPlan(
        company=company,
        user=user,
        create_company=company is None,
        create_user=user is None,
        existing_password_set=user is not None,
    )


def describe_plan(plan: BootstrapPlan) -> str:
    """Human-readable summary of the target identity and planned mutation,
    printed before any confirmation prompt. Never includes a password/hash."""
    lines = [
        "Target identity:",
        f"  company name = {TARGET_COMPANY_NAME}",
        f"  company slug = {TARGET_COMPANY_SLUG}",
        f"  email        = {TARGET_EMAIL}",
        f"  role         = {TARGET_ROLE.value}",
        "Planned mutation:",
        f"  company: {'CREATE' if plan.create_company else 'reuse existing (no change)'}",
        f"  user:    {'CREATE' if plan.create_user else 'reuse existing (no change to role/identity)'}",
    ]
    if plan.existing_password_set:
        lines.append(
            "  password: left UNTOUCHED unless --reset-existing-password is "
            "passed and the second confirmation phrase is typed"
        )
    else:
        lines.append("  password: set from operator input (new user)")
    return "\n".join(lines)


def confirm_execution(reader: Callable[[str], str] = input) -> bool:
    """Require the operator to type the primary phrase to unlock any write.

    Always interactive — takes no value from an environment variable or a
    CLI argument. Returns True only on an exact (case-sensitive) match.
    """
    print(f"\nType this exact phrase to continue: {CONFIRMATION_PHRASE}")
    return reader("> ") == CONFIRMATION_PHRASE


def confirm_reset_execution(reader: Callable[[str], str] = input) -> bool:
    """Require a second, distinct phrase before overwriting an existing
    user's password. Always interactive, never via env/CLI."""
    print(
        "\nYou are about to OVERWRITE the password of an EXISTING platform "
        f"Super Admin account ({TARGET_EMAIL}).\n"
        f"Type this exact phrase to continue: {RESET_CONFIRMATION_PHRASE}"
    )
    return reader("> ") == RESET_CONFIRMATION_PHRASE


def read_new_password(
    prompt: str = "New Super Admin password: ",
    confirm_prompt: str = "Confirm password: ",
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


def apply_plan(
    db,
    plan: BootstrapPlan,
    password: str,
    reset_existing_password: bool,
) -> tuple:
    """Perform the mutation implied by `plan`. Only called once a password has
    been read and every applicable confirmation phrase has matched.

    - Creates the company if missing.
    - Creates the user (role=SUPER_ADMIN, ACTIVE, is_active=True) if missing.
    - If the user already exists and reset_existing_password is True, resets
      its password via AuthService.get_password_hash() and revokes only its
      own refresh tokens. Otherwise the existing user is left untouched.
    - Exactly one commit.
    """
    from sqlalchemy import delete

    from app.auth.model import RefreshToken
    from app.auth.service import AuthService
    from app.companies.model import Company
    from app.users.model import User, UserStatus

    company = plan.company
    if company is None:
        company = Company(id=uuid.uuid4(), name=TARGET_COMPANY_NAME, slug=TARGET_COMPANY_SLUG)
        db.add(company)

    user = plan.user
    if user is None:
        user = User(
            id=uuid.uuid4(),
            company_id=company.id,
            email=TARGET_EMAIL,
            first_name=TARGET_FIRST_NAME,
            last_name=TARGET_LAST_NAME,
            hashed_password=AuthService.get_password_hash(password),
            role=TARGET_ROLE,
            status=UserStatus.ACTIVE,
            is_active=True,
        )
        db.add(user)
    elif reset_existing_password:
        user.hashed_password = AuthService.get_password_hash(password)
        db.add(user)
        db.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))

    db.commit()
    return company, user


def emit_audit_event(user, company_id) -> None:
    from app.auth.audit import log_otp_event

    log_otp_event(
        AUDIT_EVENT,
        email=getattr(user, "email", TARGET_EMAIL),
        user_id=getattr(user, "id", None),
        company_id=company_id,
    )


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "ONE-TIME bootstrap of the dedicated THTWAAT platform Super Admin "
            "account. By default this never overwrites an existing user's "
            "password; pass --reset-existing-password (plus a second, "
            "separate interactive confirmation phrase) to do so."
        )
    )
    parser.add_argument(
        "--reset-existing-password",
        action="store_true",
        default=False,
        help=(
            "If the target user already exists, allow resetting its password. "
            "Still requires typing a second, distinct confirmation phrase at "
            "an interactive prompt; the phrase itself is never accepted via "
            "this flag, any other argument, or an environment variable."
        ),
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)

    supplied_token = os.environ.get(ENV_BOOTSTRAP_TOKEN)
    expected_hash = os.environ.get(ENV_BOOTSTRAP_TOKEN_SHA256)
    if not verify_bootstrap_token(supplied_token, expected_hash):
        print(
            f"ERROR: {ENV_BOOTSTRAP_TOKEN} is missing or does not match "
            f"{ENV_BOOTSTRAP_TOKEN_SHA256}. Aborting before any check or write."
        )
        return 1

    # Bootstrap ORM mappers before opening a Session outside of main.py —
    # same requirement as scripts/break_glass_reset_password.py and friends.
    from app.database.orm_bootstrap import register_orm_models

    register_orm_models()

    from app.database.database import SessionLocal

    db = SessionLocal()
    try:
        try:
            plan = build_plan(db)
        except BootstrapError as exc:
            print(f"ERROR: {exc}")
            return 1

        print(describe_plan(plan))

        if not confirm_execution():
            print("Confirmation phrase did not match. Aborting before any write.")
            return 1

        do_reset = False
        if plan.existing_password_set:
            if args.reset_existing_password:
                if not confirm_reset_execution():
                    print(
                        "Reset confirmation phrase did not match. Aborting "
                        "before any write."
                    )
                    return 1
                do_reset = True
            else:
                print(
                    "Target user already exists; leaving its password "
                    "untouched (pass --reset-existing-password to change it)."
                )

        if not (plan.create_company or plan.create_user or do_reset):
            print("Nothing to do. Company and user already exist as expected.")
            return 0

        password = read_new_password()
        company, user = apply_plan(db, plan, password, reset_existing_password=do_reset)
        password = None  # best-effort scrub of the local reference

        emit_audit_event(user, company.id)

        if plan.create_user:
            print(f"Created Super Admin user {TARGET_EMAIL!r} in company {TARGET_COMPANY_SLUG!r}.")
        elif do_reset:
            print(f"Reset password for existing Super Admin user {TARGET_EMAIL!r}.")
        print("Done. Log in normally via POST /api/v1/auth/login to obtain a session.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
