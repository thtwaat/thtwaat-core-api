"""
scripts/local_provision_super_admin.py

Interactive helper that provisions the dedicated THTWAAT platform Super Admin
account, using only existing, already-authorized application API endpoints
(no direct DB writes):

    1. POST   /api/v1/companies/               (create "THTWAAT Platform" if missing)
    2. POST   /api/v1/admin/users/invite        (invite superadmin@thtwaat.com if missing)
    3. PATCH  /api/v1/users/{user_id}           (set the operator-chosen password)

Defaults to LOCAL-ONLY. Safety properties:
  - Refuses to run against a production API host (thtwaat.com or any
    *.thtwaat.com host, e.g. api.thtwaat.com) unless BOTH of the following
    are true: the operator passes --allow-production, AND the operator
    interactively types an exact confirmation phrase at a prompt. The phrase
    is never accepted via an environment variable or a CLI argument.
  - Never hardcodes a password. The new password is read interactively with
    getpass (hidden input) and confirmed by re-entry.
  - Never prints, logs, or returns the plaintext password, the admin JWT, nor
    the server-generated "temporary_password" the invite endpoint returns.
  - Only ever touches two records: the new "thtwaat-platform" company and the
    new "superadmin@thtwaat.com" user. It looks each up first and reuses it
    if it already exists instead of re-creating it.

Usage (LOCAL/dev API — default mode):

    THTWAAT_API_BASE_URL=http://localhost:8000/api/v1 \\
    THTWAAT_ADMIN_JWT=<existing super_admin JWT> \\
    python scripts/local_provision_super_admin.py

Usage (production — requires the explicit flag AND a typed confirmation):

    THTWAAT_API_BASE_URL=https://api.thtwaat.com/api/v1 \\
    python scripts/local_provision_super_admin.py --allow-production
    # (JWT and new password are still prompted for interactively; the
    #  confirmation phrase prompt is separate and always interactive)

Both env vars above are optional — if unset, the script prompts for them
interactively (the JWT prompt uses hidden input via getpass).
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from typing import Any, Callable, Optional
from urllib.parse import urlsplit

import httpx

COMPANY_NAME = "THTWAAT Platform"
COMPANY_SLUG = "thtwaat-platform"
SUPER_ADMIN_EMAIL = "superadmin@thtwaat.com"
SUPER_ADMIN_ROLE = "super_admin"
SUPER_ADMIN_FIRST_NAME = "THTWAAT"
SUPER_ADMIN_LAST_NAME = "Admin"

# Any host matching this or ending in ".thtwaat.com" is treated as production
# and refused unless explicitly and interactively unlocked. This script
# defaults to LOCAL-ONLY behavior.
PRODUCTION_APEX_HOST = "thtwaat.com"

# Must be typed verbatim, interactively, to run against a production host.
# Deliberately not accepted via any environment variable or CLI argument.
PRODUCTION_CONFIRMATION_PHRASE = "CREATE THTWAAT PLATFORM SUPER ADMIN"

ENV_BASE_URL = "THTWAAT_API_BASE_URL"
ENV_JWT = "THTWAAT_ADMIN_JWT"

# Fields safe to print about a user record. Deliberately an allow-list so a
# stray "temporary_password" / "hashed_password" key can never leak through.
_SAFE_USER_FIELDS = {"id", "email", "role", "company_id", "status", "is_active"}


class ProvisioningError(RuntimeError):
    """Raised for any local, pre-flight safety failure (not an HTTP error)."""


def is_production_host(base_url: str) -> bool:
    """True if base_url's host is thtwaat.com or any *.thtwaat.com subdomain."""
    host = (urlsplit(base_url).hostname or "").lower()
    if not host:
        raise ProvisioningError(f"Could not parse a host from base URL '{base_url}'.")
    return host == PRODUCTION_APEX_HOST or host.endswith("." + PRODUCTION_APEX_HOST)


def assert_not_production(base_url: str, *, allow_production: bool = False) -> None:
    """Refuse to target a production API host unless allow_production is set.

    This is the low-level guard: by default (allow_production=False) it
    blocks any thtwaat.com host, exactly as before. Passing
    allow_production=True lifts this specific check, but main() additionally
    requires a separate, always-interactive confirmation phrase — see
    confirm_production_execution() — before any production API call is made.
    """
    if is_production_host(base_url) and not allow_production:
        raise ProvisioningError(
            f"Refusing to run against '{base_url}': this looks like a "
            "production THTWAAT host. This helper defaults to LOCAL-ONLY; "
            "pass --allow-production (plus interactive confirmation) to override."
        )


def confirm_production_execution(reader: Callable[[str], str] = input) -> bool:
    """Require the operator to type the exact phrase to unlock production.

    Always interactive — takes no value from an environment variable or a
    CLI argument. Returns True only on an exact (case-sensitive) match.
    """
    print(
        "\nYou are about to provision the platform Super Admin against a "
        "PRODUCTION THTWAAT host.\n"
        f"Type this exact phrase to continue: {PRODUCTION_CONFIRMATION_PHRASE}"
    )
    typed = reader("> ")
    return typed == PRODUCTION_CONFIRMATION_PHRASE


def auth_headers(jwt: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jwt}"}


def build_company_payload() -> dict[str, Any]:
    """Exact body for POST /api/v1/companies/ (CompanyCreate schema)."""
    return {"name": COMPANY_NAME, "slug": COMPANY_SLUG}


def build_invite_payload(company_id: str) -> dict[str, Any]:
    """Exact body for POST /api/v1/admin/users/invite (AdminInviteUserRequest)."""
    return {
        "email": SUPER_ADMIN_EMAIL,
        "company_id": company_id,
        "role": SUPER_ADMIN_ROLE,
        "first_name": SUPER_ADMIN_FIRST_NAME,
        "last_name": SUPER_ADMIN_LAST_NAME,
    }


def build_password_patch_payload(password: str) -> dict[str, Any]:
    """Exact body for PATCH /api/v1/users/{user_id} (UserUpdate schema, password only)."""
    return {"password": password}


def summarize_user(user_payload: dict[str, Any]) -> dict[str, Any]:
    """Allow-list a user dict down to safe-to-print identifiers/status only."""
    return {k: v for k, v in user_payload.items() if k in _SAFE_USER_FIELDS}


def find_company_by_slug(
    client: httpx.Client, base_url: str, jwt: str, slug: str
) -> Optional[dict[str, Any]]:
    resp = client.get(f"{base_url}/companies/slug/{slug}", headers=auth_headers(jwt))
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def create_company(client: httpx.Client, base_url: str) -> dict[str, Any]:
    """POST /api/v1/companies/ is a public, unauthenticated endpoint."""
    resp = client.post(f"{base_url}/companies/", json=build_company_payload())
    resp.raise_for_status()
    return resp.json()


def find_user_by_email(
    client: httpx.Client, base_url: str, jwt: str, company_id: str, email: str
) -> Optional[dict[str, Any]]:
    resp = client.get(
        f"{base_url}/users/",
        params={"company_id": company_id, "q": email, "include_inactive": True},
        headers=auth_headers(jwt),
    )
    resp.raise_for_status()
    for row in resp.json().get("results", []):
        if str(row.get("email", "")).lower() == email.lower():
            return row
    return None


def invite_user(
    client: httpx.Client, base_url: str, jwt: str, company_id: str
) -> dict[str, Any]:
    """POST /api/v1/admin/users/invite.

    The response also contains a server-generated "temporary_password" —
    callers of this function must not print/log/store that field.
    """
    resp = client.post(
        f"{base_url}/admin/users/invite",
        json=build_invite_payload(company_id),
        headers=auth_headers(jwt),
    )
    resp.raise_for_status()
    return resp.json()


def set_password(
    client: httpx.Client, base_url: str, jwt: str, user_id: str, password: str
) -> dict[str, Any]:
    resp = client.patch(
        f"{base_url}/users/{user_id}",
        json=build_password_patch_payload(password),
        headers=auth_headers(jwt),
    )
    resp.raise_for_status()
    return resp.json()


def read_new_password(
    prompt: str = "New Super Admin password: ",
    confirm_prompt: str = "Confirm password: ",
    reader=getpass.getpass,
) -> str:
    """Interactively read + confirm a new password. Never echoed, never returned via print."""
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


def resolve_base_url(reader=input) -> str:
    return os.environ.get(ENV_BASE_URL) or reader(
        f"API base URL (e.g. http://localhost:8000/api/v1) [{ENV_BASE_URL} not set]: "
    ).strip()


def resolve_jwt(reader=getpass.getpass) -> str:
    jwt = os.environ.get(ENV_JWT)
    if jwt:
        return jwt
    return reader(f"Existing platform-admin JWT ({ENV_JWT} not set, input hidden): ").strip()


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Provisions the dedicated THTWAAT platform Super Admin. Defaults "
            "to LOCAL-ONLY; running against a production host additionally "
            "requires typing an exact confirmation phrase interactively."
        )
    )
    parser.add_argument(
        "--allow-production",
        action="store_true",
        default=False,
        help=(
            "Permit running against a production THTWAAT host. Still requires "
            "typing an exact confirmation phrase at an interactive prompt; "
            "the phrase itself is never accepted via this flag, any other "
            "argument, or an environment variable."
        ),
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    base_url = resolve_base_url().rstrip("/")

    try:
        production = is_production_host(base_url)
    except ProvisioningError as exc:
        print(f"ERROR: {exc}")
        return 1

    if production:
        try:
            assert_not_production(base_url, allow_production=args.allow_production)
        except ProvisioningError as exc:
            print(f"ERROR: {exc}")
            return 1
        if not confirm_production_execution():
            print("Confirmation phrase did not match. Aborting before any API call.")
            return 1
        print("Production execution confirmed. Proceeding against a PRODUCTION host.")
    elif args.allow_production:
        print("Note: --allow-production has no effect against a non-production host.")

    jwt = resolve_jwt()
    if not jwt:
        print("ERROR: an existing platform-admin JWT is required.")
        return 1

    try:
        with httpx.Client(timeout=30.0) as client:
            company = find_company_by_slug(client, base_url, jwt, COMPANY_SLUG)
            if company is None:
                print(f"Company slug '{COMPANY_SLUG}' not found - creating it...")
                company = create_company(client, base_url)
            else:
                print(f"Company slug '{COMPANY_SLUG}' already exists - reusing it.")
            company_id = str(company["id"])
            print(f"Company id: {company_id}")

            user = find_user_by_email(client, base_url, jwt, company_id, SUPER_ADMIN_EMAIL)
            if user is None:
                print(f"User '{SUPER_ADMIN_EMAIL}' not found in company - inviting...")
                invite_response = invite_user(client, base_url, jwt, company_id)
                user = invite_response["user"]
                # invite_response["temporary_password"] is intentionally never read.
            else:
                print(f"User '{SUPER_ADMIN_EMAIL}' already exists - reusing it.")
            print(f"Safe summary: {summarize_user(user)}")

            password = read_new_password()
            set_password(client, base_url, jwt, str(user["id"]), password)
            password = None  # best-effort scrub of the local reference
            print("Password updated successfully via PATCH /users/{id}. Done.")
    except httpx.HTTPStatusError as exc:
        print(
            f"ERROR: API call failed: {exc.response.status_code} "
            f"{exc.request.method} {exc.request.url}"
        )
        return 1
    except ProvisioningError as exc:
        print(f"ERROR: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
