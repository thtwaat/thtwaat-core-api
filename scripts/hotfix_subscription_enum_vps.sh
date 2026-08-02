#!/usr/bin/env bash
# Paste-friendly VPS hotfix: bind lowercase enum values + values_callable.
# Does NOT require git pull — patches files inside thtwaat-api, then restarts.
set -euo pipefail

docker exec -i thtwaat-api python3 - <<'PY'
from pathlib import Path

# --- repository: force lowercase status labels in SQL ---
repo = Path("/app/app/payments/subscriptions/repository.py")
rt = repo.read_text()
if "_ACTIVE_STATUSES" not in rt:
    rt = rt.replace(
        "from app.payments.subscriptions.model import Subscription, SubscriptionStatus, SubscriptionProvider\n",
        "from app.payments.subscriptions.model import Subscription, SubscriptionStatus, SubscriptionProvider\n\n"
        "# PG enum labels are lowercase values (active), not names (ACTIVE).\n"
        "_ACTIVE_STATUSES = (\n"
        "    SubscriptionStatus.ACTIVE.value,\n"
        "    SubscriptionStatus.TRIALING.value,\n"
        "    SubscriptionStatus.PAST_DUE.value,\n"
        ")\n",
        1,
    )
    import re
    rt, n = re.subn(
        r"Subscription\.status\.in_\(\s*\[[^\]]+\]\s*\)",
        "Subscription.status.in_(_ACTIVE_STATUSES)",
        rt,
        count=1,
    )
    if n == 0 and "Subscription.status.in_(_ACTIVE_STATUSES)" not in rt:
        raise SystemExit("could not patch get_active_by_company status filter")
    rt = rt.replace(
        "Subscription.status == SubscriptionStatus.INCOMPLETE,",
        "Subscription.status == SubscriptionStatus.INCOMPLETE.value,",
    )
    repo.write_text(rt)
    print("repository: patched")
else:
    print("repository: already has _ACTIVE_STATUSES")

# --- models: values_callable so writes also use lowercase ---
def ensure_pg_enum(path: Path, before_class: str) -> None:
    t = path.read_text()
    if "values_callable" in t and "_pg_enum" in t:
        print(f"{path.name}: already patched")
        return
    helper = (
        "\ndef _pg_enum(enum_cls, name: str):\n"
        "    return SAEnum(\n"
        "        enum_cls,\n"
        "        name=name,\n"
        "        values_callable=lambda members: [item.value for item in members],\n"
        "    )\n\n\n"
    )
    if "def _pg_enum" not in t:
        if before_class not in t:
            raise SystemExit(f"marker {before_class!r} missing in {path}")
        t = t.replace(before_class, helper + before_class, 1)
    replacements = [
        (
            'Column(SAEnum(SubscriptionProvider, name="subscription_provider_enum"), nullable=False)',
            'Column(_pg_enum(SubscriptionProvider, "subscription_provider_enum"), nullable=False)',
        ),
        (
            'Column(SAEnum(SubscriptionStatus, name="subscription_status_enum"), nullable=False, default=SubscriptionStatus.INCOMPLETE)',
            'Column(_pg_enum(SubscriptionStatus, "subscription_status_enum"), nullable=False, default=SubscriptionStatus.INCOMPLETE)',
        ),
        (
            'Column(SAEnum(InvoiceStatus, name="invoice_status_enum"), nullable=False, default=InvoiceStatus.OPEN)',
            'Column(_pg_enum(InvoiceStatus, "invoice_status_enum"), nullable=False, default=InvoiceStatus.OPEN)',
        ),
    ]
    for old, new in replacements:
        t = t.replace(old, new)
    if "values_callable" not in t:
        raise SystemExit(f"failed to add values_callable in {path}")
    path.write_text(t)
    print(f"{path.name}: patched")

ensure_pg_enum(Path("/app/app/payments/subscriptions/model.py"), "class Subscription(Base")
ensure_pg_enum(Path("/app/app/payments/invoices/model.py"), "class Invoice(Base")
print("OK")
PY

docker restart thtwaat-api
sleep 8

echo "==> Verify"
docker exec thtwaat-api grep -n "_ACTIVE_STATUSES\|values_callable" \
  /app/app/payments/subscriptions/repository.py \
  /app/app/payments/subscriptions/model.py | head -20

echo "==> plans body / code"
curl -sk -w "\nHTTP %{http_code}\n" https://api.thtwaat.com/api/v1/payments/plans/ | head -c 600
echo
echo "==> enum errors (expect none)"
docker logs thtwaat-api --tail=50 2>&1 | grep -F 'ACTIVE' || echo "(none)"
