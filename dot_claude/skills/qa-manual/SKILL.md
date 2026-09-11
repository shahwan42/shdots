---
name: qa-manual
description: Run a manual QA session for ClearMoney. Triggers on: run QA, manual testing, test the app, qa session, execute test plan, QA the feature, check for bugs, verify the app works.
---

# ClearMoney — Manual QA Session

Full guide: `docs/qa/QA-ENGINEER-GUIDE.md`

## Environment Setup (run once per session)

```bash
# 1. Start DB (Docker)
docker-compose up -d db

# 2. Check server is running
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/   # should be 302

# 3. If server not running:
DISABLE_RATE_LIMIT=true make run &

# 4. Reset QA environment (idempotent — safe to re-run)
make qa-reset EMAIL=qa@clearmoney.app PASSWORD=qatest123

# 5. Get magic link (dev mode — no email sent)
make qa-login EMAIL=qa@clearmoney.app
# → prints http://localhost:8000/auth/verify?token=XXXX
```

## Login via Playwright

```python
# If make qa-login fails, get token from DB directly:
from auth_app.models import AuthToken
t = AuthToken.objects.filter(email='qa@clearmoney.app', used=False).order_by('-created_at').first()
print(f"http://localhost:8000/auth/verify?token={t.token}")
```

Then: `mcp__playwright__browser_navigate("http://localhost:8000/auth/verify?token=XXXX")`

## Test Data Baseline (after `make qa-seed`)

| Entity | Detail |
|--------|--------|
| Institution | "QA Test Bank" |
| Account: Main Checking EGP | Current, EGP, balance ~8,300 (after seeded transactions) |
| Account: Savings EGP | Savings, EGP, balance 0 |
| Account: USD Account | Current, USD, balance 500 |
| Account: Credit Card EGP | Credit Card, EGP, balance -2,000, limit 20,000 |
| Transactions | 4 seeded: salary 5000, grocery 500, transport 200, restaurant 1000 |
| Budget: Food & Groceries | 3,000 EGP/month |
| Budget: Transport | 500 EGP/month |

## Critical Paths to Verify First

1. **CP-2**: Create transaction → verify balance decreases
2. **CP-3**: Transfer → both balances update, net worth unchanged
3. **CP-4**: Create budget → spend → verify % in budgets page
4. **CP-5**: Dashboard loads without 500 errors

## Testing Workflow

For each feature/scenario:
1. Navigate to the feature
2. Take screenshot: `mcp__playwright__browser_take_screenshot` → save to `.tickets/attachments/qa-NN-<feature>.png`
3. Execute the action
4. Verify expected outcome (UI + DB if financial data)
5. Test at least one error/edge case
6. If bug found: file ticket in `.tickets/pending/` (see template below)

## DB Verification (Python shell)

```bash
cd backend && DATABASE_URL="postgres://clearmoney:clearmoney@localhost:5433/clearmoney" uv run python -c "
import django, os; os.environ['DJANGO_SETTINGS_MODULE'] = 'clearmoney.settings'; django.setup()
from accounts.models import Account
from auth_app.models import User
u = User.objects.get(email='qa@clearmoney.app')
for a in Account.objects.filter(user_id=str(u.id)):
    print(f'{a.name}: {a.current_balance} {a.currency}')
"
```

## Bug Ticket Template

Create: `.tickets/pending/<next-id>-<slug>.md`

```markdown
---
id: "NNN"
title: "Bug: <one-line description>"
type: bug
priority: high|medium|low
status: pending
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

## Description
[Observed vs Expected]

## Steps to Reproduce
1. ...

## Screenshot
See: `.tickets/attachments/qa-NN-<name>.png`

## Acceptance Criteria
- [ ] ...
```

**Priority guide:**
- `high` — financial data integrity (wrong balance, fee dropped, currency mixup)
- `medium` — feature broken (500 error, validation missing, future dates allowed)
- `low` — UI/UX (missing maxlength, untranslated strings, noisy banners)

## Known Issues (skip these, already filed)

| # | Issue |
|---|-------|
| #118 | Liquid Cash mixes currencies without conversion |
| #119 | PDF export 500 when WeasyPrint libs missing |
| #120 | Move Money form allows future dates |
| #121 | Fee amount silently dropped on transaction create |
| #122 | Multiple form inputs missing maxlength |
| #123 | RTL section headings untranslated + "d left" fragmentation |
| #124 | Reconciliation banners shown for brand-new accounts |

## Checklist for Comprehensive QA Coverage

- [ ] Auth: login flow, expired token, used token
- [ ] Dashboard: all panels render, no 500, empty state CTA
- [ ] Transaction create: expense, income, transfer, exchange
- [ ] Transaction balance verification (DB check after each)
- [ ] Transaction edit/delete
- [ ] Transfer: valid, same-account error, different-currency error
- [ ] Fee field: create with fee, verify fee in DB and balance_delta
- [ ] Budget: create, spend, verify %, overspend warning
- [ ] Budget rollover, copy last month
- [ ] CSV import: upload → map → preview → submit → verify
- [ ] Tags: add, filter by tag, spending-by-tag report
- [ ] Search: global search with results, no results, XSS input
- [ ] Reports: donut chart, bar chart, PDF export
- [ ] Recurring rules: create, verify calendar shows event
- [ ] Virtual accounts: create, auto-allocate
- [ ] People/loans: create, track payment, net worth impact
- [ ] Settings: dark mode, language (EN↔AR), CSV export, push notifs
- [ ] RTL: layout flip, translated strings, no text fragmentation
- [ ] Reconciliation: account reconcile page
- [ ] Mobile viewport (375px): no horizontal scroll
- [ ] Accessibility: form labels, keyboard nav, focus visible
