# First-Time User Onboarding (Launch Module 4)

Production SaaS onboarding that guides a new customer from signup to a working AI agent.

## Audit summary

| Area | Status |
|------|--------|
| Backend onboarding facade (`app/onboarding/`) | **Exists** — 12-step orchestration, autosave, pause/resume, knowledge upload helper |
| APIs | **Reuse** — `POST /api/v1/onboarding/start`, `/me`, `/me/autosave`, `/me/steps/{step}/complete\|skip`, `/me/knowledge/upload` |
| Signup (SaaS) | **Restored** — now calls `/onboarding/start` (no duplicate company+user create path) |
| Login | **Improved** — redirects incomplete sessions to `/app/onboarding` |
| Email verification | **Wired** — Welcome step completes `verify_email` via OTP |
| Company / workspace | **Reuse** — `create_company` step + company profile fields |
| Provider step | **Reuse** — read-only `aiProvidersApi` (Module 1); preference stored in draft / agent `web_config` |
| Agent / knowledge / widget | **Reuse** — onboarding step executors + Agent Builder / Knowledge / embed APIs |
| SaaS wizard UI | **Added** — `/app/onboarding` 7-step guided UX over the existing 12-step backend |

**Do not rebuild** `app/onboarding` business logic. The SaaS UI compresses UX into 7 steps while completing/skipping backend steps in order.

## UI → backend mapping

| UI step | Backend actions |
|---------|-----------------|
| 1 Welcome | Intro + `verify_email` (OTP) when required; Skip → `POST /me/pause` |
| 2 Workspace | `create_company` (name, industry, logo, team_size in settings) |
| 3 AI Provider | `choose_plan` with `{ stay_free: true }` + autosave provider preference (no BYOK) |
| 4 First Agent | `create_ai_agent` with starter template prompt + `web_config` |
| 5 Knowledge | Upload via `/me/knowledge/upload` then `upload_knowledge` complete, or skip |
| 6 Widget | Skip `choose_template` → `generate_product` → `preview` → `publish` → `agentsApi.embed` |
| 7 Finish | Skip `connect_domain` → `go_live` → Dashboard |

## SaaS routes

- `/signup` → `onboardingApi.start` → tokens → `/app/onboarding`
- `/login` → if session `in_progress` → `/app/onboarding`
- `/app/onboarding` — focused wizard (no app sidebar)
- App shell redirects other `/app/*` pages to onboarding while status is `in_progress`

## UX features

- Progress bar + step chips
- Local draft (`tht_onboarding_ui_draft_v1`) + server autosave
- Validation, loading / empty / error / success toasts
- Keyboard-friendly controls, ARIA labels on progress and dropzone
- Responsive layout

## Tests

```bash
cd apps/templates/saas && npm test -- --run src/lib/onboarding.test.ts src/lib/agent-builder.test.ts
```

Backend facade coverage remains in `tests/onboarding/`.

## Related

- Backend facade: `app/onboarding/README.md`
- Agent Builder (Module 3): `docs/ops/AGENT_BUILDER_UX.md`
- AI Providers (Module 1): `docs/ops/AI_PROVIDER_MANAGEMENT_UI.md`
