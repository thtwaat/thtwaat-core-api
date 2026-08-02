#!/usr/bin/env bash
# Hotfix: GET /api/v1/payments/subscriptions/me must not 500.
# Run on VPS:  bash scripts/hotfix_billing_me_vps.sh
set -euo pipefail
cd "$(dirname "$0")/.."

REPO="app/payments/subscriptions/repository.py"
ROUTER="app/payments/subscriptions/router.py"

python3 - <<'PY'
from pathlib import Path

repo = Path("app/payments/subscriptions/repository.py")
text = repo.read_text()
# Idempotent: replace either old scalar_one_or_none OR already-patched block
import re
pattern = r"    def get_active_by_company\(self, company_id: uuid\.UUID\) -> Optional\[Subscription\]:.*?\.scalar_one_or_none\(\)"
replacement = '''    def get_active_by_company(self, company_id: uuid.UUID) -> Optional[Subscription]:
        """Newest active/trialing/past_due sub; never raises MultipleResultsFound."""
        return (
            self.db.execute(
                select(Subscription)
                .where(
                    Subscription.company_id == company_id,
                    Subscription.status.in_([
                        SubscriptionStatus.ACTIVE,
                        SubscriptionStatus.TRIALING,
                        SubscriptionStatus.PAST_DUE,
                    ]),
                )
                .order_by(Subscription.created_at.desc())
            )
            .scalars()
            .first()
        )'''
new, n = re.subn(pattern, replacement, text, count=1, flags=re.S)
if n == 0:
    if ".scalars()" in text and "get_active_by_company" in text and "first()" in text:
        print("repository already patched")
    else:
        raise SystemExit("Could not patch repository.py — unexpected file contents")
else:
    repo.write_text(new)
    print("repository patched")

router = Path("app/payments/subscriptions/router.py")
rt = router.read_text()
if "Billing data unavailable" not in rt:
    # Ensure HTTPException import
    if "HTTPException" not in rt.split("from fastapi import")[1].split("\n")[0]:
        rt = rt.replace(
            "from fastapi import APIRouter, Depends, status",
            "from fastapi import APIRouter, Depends, HTTPException, status",
        )
        rt = rt.replace(
            "from fastapi import APIRouter, Depends, HTTPException, status",
            "from fastapi import APIRouter, Depends, HTTPException, status",
        )
    old_fn = '''def get_my_subscription(
    current_user: UserProfileResponse = Depends(get_current_user),
    service: SubscriptionService = Depends(get_sub_service)
):
    """Returns the active subscription for the authenticated user's company."""
    return service.get_subscription(current_user.company_id)
'''
    # Also match docstring variants
    import re as _re
    fn_pat = _re.compile(
        r"def get_my_subscription\([\s\S]*?\n    return service\.get_subscription\(current_user\.company_id\)\n",
        _re.M,
    )
    new_fn = '''def get_my_subscription(
    current_user: UserProfileResponse = Depends(get_current_user),
    service: SubscriptionService = Depends(get_sub_service),
):
    """Active subscription or JSON null (200). DB errors -> 503."""
    import logging
    from sqlalchemy.exc import SQLAlchemyError

    log = logging.getLogger(__name__)
    try:
        sub = service.get_subscription(current_user.company_id)
    except SQLAlchemyError as exc:
        log.exception("GET /payments/subscriptions/me db error company=%s", current_user.company_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Billing data unavailable ({exc.__class__.__name__})",
        ) from exc
    if sub is None:
        return None
    try:
        return SubscriptionResponse.model_validate(sub)
    except Exception as exc:
        log.exception("GET /payments/subscriptions/me serialize error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Subscription record could not be serialized",
        ) from exc
'''
    rt2, n2 = fn_pat.subn(new_fn, rt, count=1)
    if n2 == 0:
        raise SystemExit("Could not patch get_my_subscription in router.py")
    router.write_text(rt2)
    print("router patched")
else:
    print("router already patched")
PY

echo "==> Copy into running API container (no full rebuild)"
docker cp "$REPO" thtwaat-api:/app/app/payments/subscriptions/repository.py
docker cp "$ROUTER" thtwaat-api:/app/app/payments/subscriptions/router.py
docker restart thtwaat-api
sleep 6

echo "==> Verify inside container"
docker exec thtwaat-api grep -n "first()\|Billing data unavailable\|scalar_one_or_none" \
  /app/app/payments/subscriptions/repository.py \
  /app/app/payments/subscriptions/router.py || true

echo "==> Ensure billing tables exist"
docker exec thtwaat-api alembic upgrade head || true

echo "==> Recent API errors"
docker logs thtwaat-api --tail=50 2>&1 | tail -n 50

echo "DONE. Hard-refresh https://app.thtwaat.com/app/billing"
echo "GET /payments/subscriptions/me should be 200 (body null OK)."
echo "Stripe 503 on Choose Free needs web_app rebuild (frontend still calls Stripe)."
