# Razorpay recurring subscriptions

Implements real Razorpay recurring billing (Subscription API) alongside the
pre-existing one-time Order+verify flow, which remains unchanged and in use
for any non-recurring caller.

## 1. Architecture

Two independent Razorpay flows now coexist in `app/payments/subscriptions/`:

| | One-time (legacy/still supported) | Recurring (new) |
|---|---|---|
| Razorpay object | Order | Subscription |
| Endpoints | `POST /razorpay/order`, `POST /razorpay/verify` | `POST /razorpay/subscription`, `POST /razorpay/subscription/verify` |
| Checkout.js param | `order_id` | `subscription_id` (+ `recurring: 1`) |
| Service methods | `create_razorpay_order`, `verify_razorpay_payment` | `create_razorpay_subscription`, `verify_razorpay_subscription_payment` |
| Auto-renews | No | Yes |
| `provider_subscription_id` | Never set | Set at creation time |
| `current_period_start/end` | Never set | Set by webhook |

**Plan mapping.** `Plan.razorpay_plan_id` / `Plan.razorpay_yearly_plan_id`
(pre-existing columns, previously unused) now hold the Razorpay Plan id for
the monthly/yearly interval. `SubscriptionService._ensure_razorpay_plan()`
creates one on first use if missing — amount/currency/interval always come
from the server-side `Plan` row (via `plan_price_for_region`/
`plan_currency_for_region`, forced to the `IN`/`INR` region since Razorpay
recurring is India-only in this codebase) — and never creates a second one
once an id is recorded. A second concurrent first-checkout can still create
two Razorpay Plan objects in a rare race (Razorpay has no delete-plan API);
the DB always keeps whichever id was persisted first, so this is a harmless
orphan on Razorpay's side, not a data-integrity issue locally.

**Checkout flow (recurring):**
1. `POST /payments/subscriptions/razorpay/subscription` — resolves the
   company's plan server-side, ensures a Razorpay Plan exists, calls
   `client.subscription.create()`, and immediately persists
   `provider_subscription_id` with `status=INCOMPLETE`.
2. Frontend opens Razorpay Checkout.js with `subscription_id` (recurring
   mode) — this is what triggers the e-mandate/UPI Autopay authorization
   screen, not the plain payment popup used for Orders.
3. `POST /payments/subscriptions/razorpay/subscription/verify` — verifies
   the `(payment_id, subscription_id)` signature with
   `client.utility.verify_subscription_payment_signature()`. **This does
   not activate the subscription.** It only proves the callback is genuine
   and records a bookkeeping note. Activation, `current_period_start/end`,
   and the invoice ledger entry are written exclusively by the
   `subscription.charged` (or `subscription.activated`) webhook — the only
   source that carries the real period dates and is delivered independent
   of whether the customer's browser survives the redirect.

**Cancellation.** `cancel_subscription()` now calls
`client.subscription.cancel(id, {"cancel_at_cycle_end": 1})` instead of an
immediate cancel, and only sets `cancel_at_period_end=True` locally — it
does **not** set `cancelled_at` or downgrade eagerly. The
`subscription.cancelled` webhook is what finalizes `status=CANCELLED`,
`cancelled_at`, and the downgrade-to-free. `resume_subscription()` refuses
(400) for a Razorpay subscription already scheduled to cancel: the
installed SDK (`razorpay.resources.subscription`) has no documented way to
reverse a `cancel_at_cycle_end` request, so this is refused rather than
silently desyncing local state from what Razorpay will actually do.

## 2. Webhook events handled

All in `app/payments/webhooks/router.py:razorpay_webhook`, deduplicated via
the `BillingWebhookEvent`/`claim_webhook_event` idempotency layer, plus a
second, DB-enforced idempotency layer on the payment ledger itself:
`Invoice.provider_payment_id` has a unique index (partial, non-null; see
`alembic/versions/m6a7b8c9d0e1_invoices_provider_payment_id_unique.py`), and
every invoice-creating code path (`payment.captured`, `subscription.charged`,
and `SubscriptionService.verify_razorpay_payment`) goes through
`InvoiceRepository.create_idempotent_by_payment_id()`, a get-or-create keyed
on that column. This makes "at most one invoice per real payment" true
regardless of which caller runs first, how many times a webhook is retried,
or a genuine concurrent race between two of these paths — not just an
app-level check-then-insert.

**Credits vs. metadata sync.** `SubscriptionService._activate_company_plan()`
(plan/status/limits sync **and** a one-time AI-credit grant) is only safe to
call once per real charge. It's split into `_sync_company_plan_metadata()`
(idempotent — plan/status/limits only, safe on every delivery/retry) and
`_grant_plan_credits()` (adds `plan.ai_credits` — must run exactly once per
payment). Recurring-subscription webhooks call these separately, gated on
whether `create_idempotent_by_payment_id()` actually created a new invoice
for that payment id; the legacy one-time flow (a single event *is* both the
activation and the charge) still uses the combined `_activate_company_plan()`
in one shot, but only when the invoice was newly created.

| Event | Effect |
|---|---|
| `payment.captured` | Legacy one-time Order flow. Creates the `Invoice` idempotently by `provider_payment_id` and activates the company plan (metadata + credits) only when that invoice was newly created by this call — `/razorpay/verify` may have already done both for the same payment if it ran first. |
| `payment.failed` | Notification only (unchanged) |
| `subscription.activated` | Marks `ACTIVE`, syncs plan/status/limits (`_sync_company_plan_metadata`), opportunistically records period if present. **Does not grant AI credits** — see `subscription.charged` below. Looks up by `provider_subscription_id` first (previously looked up by a stale order/payment id, which never matched anything for the old flow). |
| `subscription.charged` | **The renewal event, and the sole place AI credits are granted.** Updates `current_period_start/end`, creates the `Invoice` idempotently by `provider_payment_id`, syncs plan/status/limits every delivery, and grants AI credits only when this call actually created a new invoice for that payment id. Fires on every cycle, including the first — Razorpay sends `subscription.activated` *and* `subscription.charged` as two distinct events for cycle 1, so credits are granted from `subscription.charged` alone to avoid a double grant. Fires `subscription.renewed` + `payment.success` notifications. |
| `subscription.pending` | Razorpay is mid-retry after a failed charge. Sets `PAST_DUE`. **Does not downgrade** — the subscription is still inside Razorpay's own retry/collection window. |
| `subscription.halted` | Razorpay has exhausted its retry schedule (final failure). Sets `UNPAID` and downgrades via the existing `_downgrade_to_free` path — the same one used for a voluntary cancellation. |
| `subscription.cancelled` / `subscription.canceled` | Sets `CANCELLED`, `cancelled_at`, downgrades. (Pre-existing handler; now actually reachable since `provider_subscription_id` is populated.) |
| `refund.processed` | Notification only (unchanged) |

**Preventing a second live mandate.** `create_razorpay_subscription()`
refuses (409) if the company already has an `ACTIVE`/`TRIALING`/`PAST_DUE`
Razorpay row with a `provider_subscription_id` already set — i.e. a real,
still-billing recurring mandate. Without this guard, calling the endpoint
again (a retried checkout, switching plans via the same button) would create
a *second* live Razorpay Subscription remotely and overwrite the local row's
`provider_subscription_id`, orphaning the first — it would keep auto-charging
on Razorpay's side with no local record and no in-app way to cancel it. A
legacy one-time-order `ACTIVE` row (no `provider_subscription_id`) has no
live mandate to orphan, so it does not block starting a real recurring
subscription and may still be reused for its local row, as before.

## 3. Reconciliation (safety net for dropped webhooks)

`SubscriptionService.reconcile_razorpay_subscriptions()` finds real
recurring subscriptions (`provider_subscription_id` set — legacy one-time
rows never have one and are never touched here) whose local
`current_period_end` lapsed more than 24h ago with no follow-up webhook,
re-checks the actual status with `client.subscription.fetch()`, and resyncs
local state from that authoritative answer. It never assumes non-payment
purely from a missing webhook.

This repo already runs a Redis-driven scheduler (`scripts/scheduler.py`,
the `scheduler` service in `docker-compose.prod.yml`, ticking every
`SCHEDULER_INTERVAL_SECONDS`, default 300s) alongside a worker
(`scripts/worker.py`) — no new infrastructure (Celery/Redis/etc.) was
introduced. `tick()` now calls reconciliation on an hourly throttle key
(`thtwaat:billing:razorpay_reconcile:tick`), mirroring the existing
daily-idempotent-key pattern used for enterprise retention, agent purge,
etc. in the same file.

**Remaining gap:** the scheduler container must actually be deployed and
running for this safety net to fire — confirm the `scheduler` service is
up in production (it is defined in `docker-compose.prod.yml`, but this
change does not itself deploy or restart it).

## 4. Legacy one-time Razorpay customers

Existing `Subscription` rows created by the old order-flow have
`provider=='razorpay'` and `provider_subscription_id IS NULL` — that NULL
is the identifying marker; **no migration was run and no existing row was
modified by this change.** They keep their current `ACTIVE` status and
entitlements exactly as before: no auto-expiry, no auto-conversion into a
recurring subscription.

`GET /payments/admin/analytics` now reports `legacy_one_time_razorpay_subscriptions`
and `recurring_subscriptions` separately, and **excludes** legacy rows (and
any Razorpay row whose `current_period_end` isn't set and in the future)
from `mrr`/`arr`. Stripe and manual-provider reporting is unchanged.

Policy going forward (manual/ops decision, not automated by this change):
either reach out to these customers to move them onto the new recurring
checkout, or treat them as manually-renewed fixed-term customers. Neither
is enforced by code.

## 5. Required Razorpay Dashboard configuration

- **Enable Subscriptions** on the account — this is a separate activation
  from plain Orders/Payments and requires KYC completion; request it from
  Razorpay if not already enabled.
- **Webhook** must include, in addition to whatever is already configured:
  `subscription.activated`, `subscription.charged`, `subscription.pending`,
  `subscription.halted`, `subscription.cancelled` (or `subscription.canceled`).
  `subscription.charged` was previously **not** wired up at all — without
  it nothing renews.
- **e-mandate / UPI Autopay / e-NACH** must be enabled for the account —
  required by RBI regulation for any INR recurring debit. This changes the
  customer-facing checkout screen (mandate authorization) versus the plain
  one-time Order popup.
- **Subscription cycle limit**: Razorpay's `Subscription.create` requires a
  `total_count` (number of billing cycles) — there is no literal
  "until cancelled" option. This code defaults to
  `RAZORPAY_SUBSCRIPTION_TOTAL_COUNT_MONTHLY=120` (10 years) and
  `RAZORPAY_SUBSCRIPTION_TOTAL_COUNT_YEARLY=15`, approximating indefinite
  billing. **Confirm against the actual max cycle count Razorpay allows for
  the merchant account/plan period in the Dashboard before go-live** — this
  codebase cannot query that limit, and if the real cap is lower than the
  default, `subscription.create` will reject the payload.

## 6. Environment variables

No new required variables. Existing `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`,
`RAZORPAY_WEBHOOK_SECRET`, `BILLING_ENABLE_RAZORPAY` are reused as-is. Two
new optional settings with in-code defaults (override only if the Dashboard
cycle limit differs — see above):

```
RAZORPAY_SUBSCRIPTION_TOTAL_COUNT_MONTHLY=120
RAZORPAY_SUBSCRIPTION_TOTAL_COUNT_YEARLY=15
```

## 7. Test-mode end-to-end procedure

1. Use Razorpay **test-mode** keys only (never live) — set
   `RAZORPAY_KEY_ID`/`RAZORPAY_KEY_SECRET` to the test-mode pair in a local
   `.env`, never `.env.prod`.
2. `POST /payments/subscriptions/razorpay/subscription` for a plan with a
   positive `price_inr` — confirm a `razorpay_plan_id` appears on the `Plan`
   row after the first call (Dashboard → Subscriptions → Plans) and is
   reused (no new Plan object) on a second call.
3. Complete the Checkout.js mandate flow using Razorpay's documented test
   UPI/card credentials for subscriptions.
4. Use the Razorpay Dashboard's webhook test-send feature (or the CLI) to
   fire `subscription.charged` for the created subscription id — confirm
   `current_period_start/end` populate and exactly one `Invoice` row is
   created; re-send the same event and confirm no second invoice appears.
5. Fire `subscription.pending`, then `subscription.halted` — confirm
   `PAST_DUE` then `UNPAID` + downgrade, and that `payment.failed`
   notifications fire without an intermediate downgrade on `pending`.
6. Call `POST /payments/subscriptions/cancel` — confirm
   `client.subscription.cancel` was invoked with `cancel_at_cycle_end: 1`
   (Dashboard shows the subscription still active until cycle end), then
   fire `subscription.cancelled` and confirm the local downgrade.
7. Run `SubscriptionService(db).reconcile_razorpay_subscriptions()` (or
   wait for the scheduler tick) against a subscription with a manually
   backdated `current_period_end` to exercise the safety net.

## 8. Known limitations / explicit scope-outs

- **Coupons are not supported on the recurring endpoint.** A Razorpay
  Subscription's price is fixed by its Plan object; applying a coupon would
  require a Razorpay Offer mapped to the coupon (`BillingCoupon.razorpay_offer_id`
  exists but is unused here). The frontend refuses checkout with a coupon
  applied rather than silently charging full price. The one-time Order flow
  is unaffected and keeps full coupon support.
- **No entitlement-enforcement middleware exists** for `CompanyStatus` in
  general (not introduced or fixed by this change) — downgrading via
  `_downgrade_to_free` has real effect (reduces usage-meter limits, which
  *are* enforced), but this is the same mechanism already used for
  Stripe/manual cancellations, not a new gate.
- **Migration prerequisite:** `m6a7b8c9d0e1_invoices_provider_payment_id_unique`
  adds a unique index on `invoices.provider_payment_id`. If this environment's
  `invoices` table predates the idempotency fix above, it may already contain
  duplicate `provider_payment_id` rows created by the bug this migration
  closes. Run the duplicate-check query in that migration's `upgrade()`
  docstring first and reconcile/void any extras — the migration will fail
  loudly (not silently drop rows) if duplicates are still present.
- **Not yet fixed (tracked separately, not part of this change):** the
  webhook-claim reclaim path (`claim_webhook_event`) takes no row lock, so two
  near-simultaneous deliveries of the same not-yet-processed event could
  still both enter a handler concurrently; and `reconcile_razorpay_subscriptions()`
  only considers rows with a non-null `current_period_end`, so a subscription
  that reached `subscription.activated` but never received a successful
  `subscription.charged` would not be caught by the safety net. The new
  `invoices.provider_payment_id` unique index closes the *financial-ledger*
  half of the first risk; the webhook-claim locking itself is unchanged.
