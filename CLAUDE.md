# RE Deadline Tracker — Colorado

## What this is
A web app for tracking all deadlines and to-dos across every real estate transaction. Built for a Colorado buyer's/seller's agent (single-user, residential resale only). Uses Colorado Contract to Buy and Sell (CBS) terminology throughout.

## How to run
```bash
pip3 install flask apscheduler --break-system-packages   # one-time setup
python3 app.py                                            # start the app
# Open http://localhost:5000
```

## Tech stack
- **Backend:** Python 3 + Flask + SQLite (`real_estate.db`)
- **Frontend:** Vanilla JS SPA + Bootstrap 5 (CDN) + Font Awesome (CDN)
- **Notifications:** APScheduler (background thread) + smtplib
- **No build step required**

## File structure
```
app.py                  # Flask backend — all routes, DB, templates
templates/index.html    # Main SPA shell — all modals and views
templates/shared.html   # Public read-only transaction view (/view/<token>)
static/js/app.js        # All frontend JS — state, API calls, rendering
static/css/styles.css   # Custom styles
real_estate.db          # SQLite database (auto-created, do not delete)
requirements.txt        # flask, apscheduler
```

## Database tables
- `transactions` — one row per deal (address, MEC date, closing date, all contacts)
- `deadlines` — one row per deadline, linked to a transaction via `transaction_id`
- `settings` — key/value store for email/SMTP config
- `share_tokens` — read-only share links for TC/lender/co-op agent
- `notification_log` — tracks sent email notifications (prevents duplicates)

## Key features built
1. **Dashboard** — stat cards (active/overdue/due today/due this week), alert banners, transaction grid
2. **CO CBS Import** — mirrors Section 3 of the CO Contract to Buy and Sell; all 28 named deadlines auto-calculated from MEC date, agent just confirms/overrides dates
3. **CO CBS Templates** — 4 pre-built: Buyer 30-day, Buyer 45-day, Seller 30-day, Seller 45-day
4. **Deadline management** — grouped by urgency (overdue/today/upcoming/done), one-click complete/waive/expire/reopen
5. **Share links** — generate a `/view/<token>` URL for TC, lender, or co-op agent (read-only, no login)
6. **Email notifications** — daily digest via SMTP; configure in Settings (gear icon, bottom-right)
7. **Reports** — active pipeline value, YTD closed count and volume
8. **Schema migration** — `init_db()` auto-adds new columns to existing databases on startup

## Colorado CBS deadline keys (Section 3)
`aem`, `nla`, `nlt`, `bci`, `dbc`, `eld`, `elo`, `elr`, `elt`, `apd`, `aod`, `ard`, `nlc`, `iod`, `ird`, `pit`, `ddd`, `ddr`, `eid`, `ada_eval`, `trd`, `srd`, `add_docs`, `adt`, `rfr`, `lbp`, `closing`, `possession`

## What the agent told us about their workflow
- Colorado only, residential resale, single agent (no dual agency)
- 1–2 transactions now, targeting 40+/year
- Personally tracks deadlines, TC assists
- Uses Follow Up Boss (CRM), Skyslope (docs), CTM (contracts)
- Needs: email/text alerts, shareable views for TC/lender/other agent
- Future: CTM/Skyslope API integration, multi-user support, new construction

## Known gaps / next priorities
- [ ] SMS/text notifications (Twilio integration)
- [ ] CTM eContracts API import (auto-pull dates from executed contract)
- [ ] Skyslope integration
- [ ] Follow Up Boss webhook sync
- [ ] Multi-user / team access with login
- [ ] New construction deadline template
- [ ] Mobile-optimized UI
- [ ] Calendar view of all deadlines across all transactions

## Branch
`claude/real-estate-deadline-tracker-nDAoy`
