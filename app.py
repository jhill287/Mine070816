"""
Real Estate Transaction Deadline Tracker — Colorado Edition
Flask + SQLite backend
"""

import os
import smtplib
import secrets
import json
from datetime import datetime, date, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from flask import Flask, render_template, request, jsonify, abort

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), 'real_estate.db')

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def get_db():
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS transactions (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            address          TEXT    NOT NULL,
            city             TEXT,
            state            TEXT    DEFAULT 'CO',
            zip_code         TEXT,
            mls_number       TEXT,
            type             TEXT    NOT NULL DEFAULT 'buyer',
            status           TEXT    NOT NULL DEFAULT 'active',
            mec_date         TEXT,
            closing_date     TEXT,
            possession_date  TEXT,
            purchase_price   REAL,
            client_name      TEXT,
            client_phone     TEXT,
            client_email     TEXT,
            agent_name       TEXT,
            co_agent         TEXT,
            lender_name      TEXT,
            lender_phone     TEXT,
            lender_email     TEXT,
            title_company    TEXT,
            title_contact    TEXT,
            title_phone      TEXT,
            other_agent_name TEXT,
            other_agent_phone TEXT,
            tc_name          TEXT,
            tc_email         TEXT,
            hoa_name         TEXT,
            earnest_money    REAL,
            notes            TEXT,
            created_at       TEXT    DEFAULT (datetime('now')),
            updated_at       TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS deadlines (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id  INTEGER NOT NULL,
            cbs_key         TEXT,
            title           TEXT    NOT NULL,
            description     TEXT,
            due_date        TEXT    NOT NULL,
            due_time        TEXT    DEFAULT '17:00',
            status          TEXT    NOT NULL DEFAULT 'pending',
            category        TEXT    DEFAULT 'custom',
            priority        TEXT    DEFAULT 'medium',
            completed_at    TEXT,
            completed_by    TEXT,
            notes           TEXT,
            created_at      TEXT    DEFAULT (datetime('now')),
            updated_at      TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (transaction_id) REFERENCES transactions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS share_tokens (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            token          TEXT    NOT NULL UNIQUE,
            transaction_id INTEGER NOT NULL,
            label          TEXT,
            created_at     TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (transaction_id) REFERENCES transactions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS notification_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            deadline_id INTEGER,
            notified_at TEXT    DEFAULT (datetime('now')),
            lead_days   INTEGER
        );
    ''')
    conn.commit()

    # ── Schema migrations: add new columns to existing databases ──
    new_tx_cols = [
        ('mec_date',          'TEXT'),
        ('possession_date',   'TEXT'),
        ('earnest_money',     'REAL'),
        ('lender_email',      'TEXT'),
        ('title_phone',       'TEXT'),
        ('other_agent_name',  'TEXT'),
        ('other_agent_phone', 'TEXT'),
        ('tc_name',           'TEXT'),
        ('tc_email',          'TEXT'),
        ('hoa_name',          'TEXT'),
    ]
    existing_tx_cols = {row[1] for row in conn.execute("PRAGMA table_info(transactions)").fetchall()}
    for col, coltype in new_tx_cols:
        if col not in existing_tx_cols:
            conn.execute(f"ALTER TABLE transactions ADD COLUMN {col} {coltype}")

    new_dl_cols = [('cbs_key', 'TEXT')]
    existing_dl_cols = {row[1] for row in conn.execute("PRAGMA table_info(deadlines)").fetchall()}
    for col, coltype in new_dl_cols:
        if col not in existing_dl_cols:
            conn.execute(f"ALTER TABLE deadlines ADD COLUMN {col} {coltype}")

    # Rename contract_date -> mec_date if old schema still has it
    if 'contract_date' in existing_tx_cols and 'mec_date' in existing_tx_cols:
        conn.execute("UPDATE transactions SET mec_date = contract_date WHERE mec_date IS NULL AND contract_date IS NOT NULL")

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Settings helpers
# ---------------------------------------------------------------------------

def get_setting(key, default=None):
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row['value'] if row else default


def set_setting(key, value):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, value))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Colorado CBS deadline definitions
# Matches Section 3 – Dates and Deadlines of the CO Contract to Buy and Sell
# ---------------------------------------------------------------------------

CO_CBS_DEADLINES = [
    # ── Earnest Money ──────────────────────────────────────────────────────
    {
        'key': 'aem', 'section': 'Earnest Money',
        'title': 'Alternative Earnest Money Deadline',
        'category': 'earnest_money', 'priority': 'high',
        'default_days': 3, 'default_enabled': False,
        'description': 'Deadline for delivery of alternative form of earnest money (if applicable)',
        'side': 'both',
    },

    # ── Loan – New ──────────────────────────────────────────────────────────
    {
        'key': 'nla', 'section': 'Loan – New',
        'title': 'New Loan Application Deadline',
        'category': 'financing', 'priority': 'high',
        'default_days': 3, 'default_enabled': True,
        'description': 'Buyer must apply for new loan(s) by this date',
        'side': 'buyer',
    },
    {
        'key': 'nlt', 'section': 'Loan – New',
        'title': 'New Loan Terms Deadline',
        'category': 'financing', 'priority': 'high',
        'default_days': None, 'default_enabled': True,
        'description': 'Loan terms must be acceptable to buyer (rate, amount, costs)',
        'side': 'buyer',
    },
    {
        'key': 'bci', 'section': 'Loan – New',
        'title': "Buyer's Credit Information Deadline",
        'category': 'financing', 'priority': 'medium',
        'default_days': None, 'default_enabled': False,
        'description': "Buyer provides credit information to seller",
        'side': 'both',
    },
    {
        'key': 'dbc', 'section': 'Loan – New',
        'title': "Disapproval of Buyer's Credit Information Deadline",
        'category': 'financing', 'priority': 'medium',
        'default_days': None, 'default_enabled': False,
        'description': "Seller may disapprove buyer's credit information",
        'side': 'both',
    },

    # ── Loan – Existing / Assumable ─────────────────────────────────────────
    {
        'key': 'eld', 'section': 'Loan – Existing/Assumable',
        'title': 'Existing Loan Documents Deadline',
        'category': 'financing', 'priority': 'high',
        'default_days': None, 'default_enabled': False,
        'description': 'Seller delivers existing loan documents to buyer',
        'side': 'both',
    },
    {
        'key': 'elo', 'section': 'Loan – Existing/Assumable',
        'title': 'Existing Loan Documents Objection Deadline',
        'category': 'financing', 'priority': 'high',
        'default_days': None, 'default_enabled': False,
        'description': 'Buyer may object to existing loan documents',
        'side': 'both',
    },
    {
        'key': 'elr', 'section': 'Loan – Existing/Assumable',
        'title': 'Existing Loan Review Deadline',
        'category': 'financing', 'priority': 'high',
        'default_days': None, 'default_enabled': False,
        'description': 'Buyer reviews existing loan terms and conditions',
        'side': 'both',
    },
    {
        'key': 'elt', 'section': 'Loan – Existing/Assumable',
        'title': 'Existing Loan Termination Deadline',
        'category': 'financing', 'priority': 'high',
        'default_days': None, 'default_enabled': False,
        'description': 'Buyer may terminate due to unacceptable existing loan terms',
        'side': 'both',
    },

    # ── Appraisal ────────────────────────────────────────────────────────────
    {
        'key': 'apd', 'section': 'Appraisal',
        'title': 'Appraisal Deadline',
        'category': 'appraisal', 'priority': 'high',
        'default_days': 18, 'default_enabled': True,
        'description': 'Appraisal must be completed and results received',
        'side': 'both',
    },
    {
        'key': 'aod', 'section': 'Appraisal',
        'title': 'Appraisal Objection Deadline',
        'category': 'appraisal', 'priority': 'high',
        'default_days': 19, 'default_enabled': True,
        'description': 'Buyer may object if appraised value is below purchase price',
        'side': 'buyer',
    },
    {
        'key': 'ard', 'section': 'Appraisal',
        'title': 'Appraisal Resolution Deadline',
        'category': 'appraisal', 'priority': 'high',
        'default_days': 21, 'default_enabled': True,
        'description': 'Parties must resolve the appraisal objection by this date',
        'side': 'both',
    },

    # ── New Loan Conditions ──────────────────────────────────────────────────
    {
        'key': 'nlc', 'section': 'New Loan Conditions',
        'title': 'New Loan Conditions Deadline',
        'category': 'financing', 'priority': 'high',
        'default_days': 21, 'default_enabled': True,
        'description': 'All lender conditions must be satisfied — Clear to Close',
        'side': 'both',
    },

    # ── Inspection & Due Diligence ───────────────────────────────────────────
    {
        'key': 'iod', 'section': 'Inspection & Due Diligence',
        'title': 'Inspection Objection Deadline',
        'category': 'inspection', 'priority': 'high',
        'default_days': 10, 'default_enabled': True,
        'description': 'Deadline to submit Inspection Objection Notice or terminate',
        'side': 'buyer',
    },
    {
        'key': 'ird', 'section': 'Inspection & Due Diligence',
        'title': 'Inspection Resolution Deadline',
        'category': 'inspection', 'priority': 'high',
        'default_days': 15, 'default_enabled': True,
        'description': 'Deadline to resolve all inspection objections',
        'side': 'both',
    },
    {
        'key': 'pit', 'section': 'Inspection & Due Diligence',
        'title': 'Property Insurance Termination Deadline',
        'category': 'insurance', 'priority': 'high',
        'default_days': 18, 'default_enabled': True,
        'description': 'Buyer may terminate if unable to obtain satisfactory property insurance',
        'side': 'buyer',
    },
    {
        'key': 'ddd', 'section': 'Inspection & Due Diligence',
        'title': 'Due Diligence Documents Delivery Deadline',
        'category': 'disclosure', 'priority': 'medium',
        'default_days': 7, 'default_enabled': True,
        'description': 'Seller must deliver all due diligence / off-record matters documents',
        'side': 'seller',
    },
    {
        'key': 'ddr', 'section': 'Inspection & Due Diligence',
        'title': 'Due Diligence Documents Review Deadline',
        'category': 'disclosure', 'priority': 'high',
        'default_days': 10, 'default_enabled': True,
        'description': 'Buyer reviews due diligence documents — may object or terminate',
        'side': 'buyer',
    },
    {
        'key': 'eid', 'section': 'Inspection & Due Diligence',
        'title': 'Environmental Inspection Objection Deadline',
        'category': 'inspection', 'priority': 'medium',
        'default_days': 10, 'default_enabled': False,
        'description': 'Objection deadline for environmental inspection results',
        'side': 'buyer',
    },
    {
        'key': 'ada_eval', 'section': 'Inspection & Due Diligence',
        'title': 'ADA Evaluation Deadline',
        'category': 'inspection', 'priority': 'low',
        'default_days': 10, 'default_enabled': False,
        'description': 'ADA compliance evaluation deadline',
        'side': 'buyer',
    },

    # ── Title & Survey ───────────────────────────────────────────────────────
    {
        'key': 'trd', 'section': 'Title & Survey',
        'title': 'Title Review Deadline',
        'category': 'title', 'priority': 'high',
        'default_days': 19, 'default_enabled': True,
        'description': 'Deadline to review title commitment and object to title matters',
        'side': 'buyer',
    },
    {
        'key': 'srd', 'section': 'Title & Survey',
        'title': 'Survey Review Deadline',
        'category': 'survey', 'priority': 'medium',
        'default_days': None, 'default_enabled': False,
        'description': 'Deadline to review survey for encroachments or easements',
        'side': 'buyer',
    },

    # ── HOA / Association ────────────────────────────────────────────────────
    {
        'key': 'add_docs', 'section': 'HOA / Association',
        'title': 'Association Documents Delivery Deadline',
        'category': 'hoa', 'priority': 'medium',
        'default_days': 7, 'default_enabled': False,
        'description': 'Seller delivers HOA documents, financials, meeting minutes, rules',
        'side': 'seller',
    },
    {
        'key': 'adt', 'section': 'HOA / Association',
        'title': 'Association Documents Termination Deadline',
        'category': 'hoa', 'priority': 'high',
        'default_days': 19, 'default_enabled': False,
        'description': 'Buyer may terminate if HOA documents are unsatisfactory',
        'side': 'buyer',
    },

    # ── Other ────────────────────────────────────────────────────────────────
    {
        'key': 'rfr', 'section': 'Other',
        'title': 'Right of First Refusal Deadline',
        'category': 'custom', 'priority': 'medium',
        'default_days': None, 'default_enabled': False,
        'description': 'Third-party right of first refusal must be resolved by this date',
        'side': 'both',
    },
    {
        'key': 'lbp', 'section': 'Other',
        'title': 'Lead-Based Paint Termination Deadline',
        'category': 'inspection', 'priority': 'high',
        'default_days': 10, 'default_enabled': False,
        'description': 'Terminate due to lead-based paint concerns (pre-1978 homes only)',
        'side': 'buyer',
    },

    # ── Closing ──────────────────────────────────────────────────────────────
    {
        'key': 'closing', 'section': 'Closing',
        'title': 'Closing Date',
        'category': 'closing', 'priority': 'high',
        'default_days': 30, 'default_enabled': True,
        'description': 'Property closing and settlement — sign docs and transfer title',
        'side': 'both',
    },
    {
        'key': 'possession', 'section': 'Closing',
        'title': 'Possession Date / Time',
        'category': 'closing', 'priority': 'high',
        'default_days': 30, 'default_enabled': True,
        'description': 'Date and time buyer takes possession of the property',
        'side': 'both',
    },
]

# Standard CO CBS templates (use the CO CBS defaults as a starting point)
CO_CBS_BUYER_DEFAULTS = {d['key']: d for d in CO_CBS_DEADLINES}

DEADLINE_TEMPLATES = {
    'co_cbs_buyer_30': {
        'name': 'CO CBS — Buyer Side (30-Day Close)',
        'type': 'buyer',
        'deadlines': [
            d for d in CO_CBS_DEADLINES
            if d['default_enabled'] and d['side'] in ('buyer', 'both')
               and d['default_days'] is not None
        ],
    },
    'co_cbs_buyer_45': {
        'name': 'CO CBS — Buyer Side (45-Day Close)',
        'type': 'buyer',
        'deadlines': [
            dict(d, default_days=d['default_days'] + 15 if d['default_days'] else None)
            for d in CO_CBS_DEADLINES
            if d['default_enabled'] and d['side'] in ('buyer', 'both')
               and d['default_days'] is not None
        ],
    },
    'co_cbs_seller_30': {
        'name': 'CO CBS — Seller Side (30-Day Close)',
        'type': 'seller',
        'deadlines': [
            d for d in CO_CBS_DEADLINES
            if d['default_enabled'] and d['side'] in ('seller', 'both')
               and d['default_days'] is not None
        ],
    },
    'co_cbs_seller_45': {
        'name': 'CO CBS — Seller Side (45-Day Close)',
        'type': 'seller',
        'deadlines': [
            dict(d, default_days=d['default_days'] + 15 if d['default_days'] else None)
            for d in CO_CBS_DEADLINES
            if d['default_enabled'] and d['side'] in ('seller', 'both')
               and d['default_days'] is not None
        ],
    },
}


# ---------------------------------------------------------------------------
# Email notification
# ---------------------------------------------------------------------------

def send_email(subject, body_html, to_email=None):
    """Send an email using configured SMTP settings."""
    smtp_host  = get_setting('smtp_host', '')
    smtp_port  = int(get_setting('smtp_port', '587'))
    smtp_user  = get_setting('smtp_user', '')
    smtp_pass  = get_setting('smtp_pass', '')
    from_email = get_setting('from_email', smtp_user)
    if not to_email:
        to_email = get_setting('notify_email', '')

    if not all([smtp_host, smtp_user, smtp_pass, to_email]):
        return False, 'SMTP not configured'

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = from_email
        msg['To']      = to_email
        msg.attach(MIMEText(body_html, 'html'))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(from_email, to_email, msg.as_string())
        return True, 'sent'
    except Exception as e:
        return False, str(e)


def build_digest_email(overdue, due_soon):
    today_fmt = date.today().strftime('%B %d, %Y')
    lines = [f'<h2 style="color:#1a3a5c">RE Deadline Digest — {today_fmt}</h2>']

    if overdue:
        lines.append('<h3 style="color:#dc3545">⚠ Overdue Deadlines</h3><ul>')
        for d in overdue:
            delta = (date.today() - date.fromisoformat(d['due_date'])).days
            lines.append(
                f'<li><strong>{d["address"]}</strong> — {d["title"]} '
                f'<span style="color:#dc3545">({delta} day{"s" if delta!=1 else ""} overdue)</span></li>'
            )
        lines.append('</ul>')

    if due_soon:
        lines.append('<h3 style="color:#b45309">📅 Coming Up</h3><ul>')
        for d in due_soon:
            delta = (date.fromisoformat(d['due_date']) - date.today()).days
            label = 'today' if delta == 0 else f'in {delta} day{"s" if delta!=1 else ""}'
            lines.append(
                f'<li><strong>{d["address"]}</strong> — {d["title"]} '
                f'<span style="color:#b45309">({label})</span></li>'
            )
        lines.append('</ul>')

    if not overdue and not due_soon:
        lines.append('<p style="color:#16a34a">✅ No overdue or upcoming deadlines today.</p>')

    lines.append('<p style="font-size:12px;color:#94a3b8;margin-top:24px">RE Deadline Tracker — Colorado</p>')
    return ''.join(lines)


def run_notification_check():
    """Background job: send email digest for overdue + upcoming deadlines."""
    if get_setting('notify_enabled', '0') != '1':
        return

    conn = get_db()
    today = date.today().isoformat()
    lead_days = int(get_setting('notify_lead_days', '3'))
    horizon   = (date.today() + timedelta(days=lead_days)).isoformat()

    overdue = [dict(r) for r in conn.execute(
        "SELECT d.*, t.address FROM deadlines d JOIN transactions t ON d.transaction_id=t.id "
        "WHERE d.status='pending' AND d.due_date < ? AND t.status IN ('active','under_contract') "
        "ORDER BY d.due_date", (today,)
    ).fetchall()]

    due_soon = [dict(r) for r in conn.execute(
        "SELECT d.*, t.address FROM deadlines d JOIN transactions t ON d.transaction_id=t.id "
        "WHERE d.status='pending' AND d.due_date BETWEEN ? AND ? "
        "AND t.status IN ('active','under_contract') ORDER BY d.due_date", (today, horizon)
    ).fetchall()]
    conn.close()

    if not overdue and not due_soon:
        return

    subject = f'RE Deadlines — {len(overdue)} overdue, {len(due_soon)} upcoming'
    body    = build_digest_email(overdue, due_soon)
    send_email(subject, body)


def start_scheduler():
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        hour = int(get_setting('notify_hour', '7'))
        sched = BackgroundScheduler()
        sched.add_job(run_notification_check, 'cron', hour=hour, minute=0)
        sched.start()
    except ImportError:
        pass  # APScheduler not installed — notifications disabled


# ---------------------------------------------------------------------------
# Routes — pages
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/view/<token>')
def shared_view(token):
    conn = get_db()
    row = conn.execute("SELECT * FROM share_tokens WHERE token=?", (token,)).fetchone()
    if not row:
        conn.close()
        abort(404)
    tx_row = conn.execute("SELECT * FROM transactions WHERE id=?", (row['transaction_id'],)).fetchone()
    if not tx_row:
        conn.close()
        abort(404)
    tx = dict(tx_row)
    tx['deadlines'] = [dict(d) for d in conn.execute(
        "SELECT * FROM deadlines WHERE transaction_id=? ORDER BY due_date, due_time", (tx['id'],)
    ).fetchall()]
    conn.close()
    return render_template('shared.html', tx=tx,
                           label=row['label'] or 'Shared Transaction View',
                           now_iso=date.today().isoformat())


# ---------------------------------------------------------------------------
# Routes — dashboard / alerts
# ---------------------------------------------------------------------------

@app.route('/api/dashboard')
def dashboard():
    conn = get_db()
    today    = date.today().isoformat()
    week_out = (date.today() + timedelta(days=7)).isoformat()
    stats = {
        'total_active': conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE status IN ('active','under_contract')"
        ).fetchone()[0],
        'overdue': conn.execute(
            "SELECT COUNT(*) FROM deadlines d JOIN transactions t ON d.transaction_id=t.id "
            "WHERE d.status='pending' AND d.due_date < ? AND t.status IN ('active','under_contract')", (today,)
        ).fetchone()[0],
        'due_today': conn.execute(
            "SELECT COUNT(*) FROM deadlines d JOIN transactions t ON d.transaction_id=t.id "
            "WHERE d.status='pending' AND d.due_date = ? AND t.status IN ('active','under_contract')", (today,)
        ).fetchone()[0],
        'due_this_week': conn.execute(
            "SELECT COUNT(*) FROM deadlines d JOIN transactions t ON d.transaction_id=t.id "
            "WHERE d.status='pending' AND d.due_date > ? AND d.due_date <= ? "
            "AND t.status IN ('active','under_contract')", (today, week_out)
        ).fetchone()[0],
        'total_closed': conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE status='closed'"
        ).fetchone()[0],
    }
    conn.close()
    return jsonify(stats)


@app.route('/api/alerts')
def alerts():
    conn = get_db()
    today      = date.today().isoformat()
    three_days = (date.today() + timedelta(days=3)).isoformat()
    overdue = [dict(r) for r in conn.execute(
        "SELECT d.*, t.address, t.client_name FROM deadlines d "
        "JOIN transactions t ON d.transaction_id=t.id "
        "WHERE d.status='pending' AND d.due_date < ? AND t.status IN ('active','under_contract') "
        "ORDER BY d.due_date", (today,)
    ).fetchall()]
    due_soon = [dict(r) for r in conn.execute(
        "SELECT d.*, t.address, t.client_name FROM deadlines d "
        "JOIN transactions t ON d.transaction_id=t.id "
        "WHERE d.status='pending' AND d.due_date >= ? AND d.due_date <= ? "
        "AND t.status IN ('active','under_contract') ORDER BY d.due_date", (today, three_days)
    ).fetchall()]
    conn.close()
    return jsonify({'overdue': overdue, 'due_soon': due_soon})


# ---------------------------------------------------------------------------
# Routes — transactions CRUD
# ---------------------------------------------------------------------------

@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    conn  = get_db()
    today = date.today().isoformat()
    status_filter = request.args.get('status', '')
    search        = request.args.get('search', '')
    query  = "SELECT * FROM transactions WHERE 1=1"
    params = []
    if status_filter:
        query += " AND status=?"; params.append(status_filter)
    if search:
        query += " AND (address LIKE ? OR client_name LIKE ? OR mls_number LIKE ?)"
        params.extend([f'%{search}%'] * 3)
    query += (" ORDER BY CASE status WHEN 'active' THEN 1 WHEN 'under_contract' THEN 2 "
              "WHEN 'closed' THEN 3 ELSE 4 END, created_at DESC")
    txs = [dict(t) for t in conn.execute(query, params).fetchall()]
    for t in txs:
        rows = conn.execute(
            "SELECT * FROM deadlines WHERE transaction_id=? AND status='pending' ORDER BY due_date",
            (t['id'],)
        ).fetchall()
        t['total_deadlines']   = conn.execute("SELECT COUNT(*) FROM deadlines WHERE transaction_id=?", (t['id'],)).fetchone()[0]
        t['pending_deadlines'] = len(rows)
        t['overdue_count']     = sum(1 for d in rows if d['due_date'] < today)
        upcoming = [d for d in rows if d['due_date'] >= today]
        t['next_deadline'] = dict(upcoming[0]) if upcoming else (dict(rows[0]) if rows else None)
    conn.close()
    return jsonify(txs)


@app.route('/api/transactions', methods=['POST'])
def create_transaction():
    data = request.json or {}
    conn = get_db()
    cur = conn.execute('''
        INSERT INTO transactions
          (address, city, state, zip_code, mls_number, type, status,
           mec_date, closing_date, possession_date, purchase_price, earnest_money,
           client_name, client_phone, client_email,
           agent_name, co_agent,
           lender_name, lender_phone, lender_email,
           title_company, title_contact, title_phone,
           other_agent_name, other_agent_phone, tc_name, tc_email,
           hoa_name, notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ''', _tx_params(data))
    tid = cur.lastrowid
    conn.commit()
    tpl = data.get('template')
    if tpl and tpl in DEADLINE_TEMPLATES:
        _apply_template(conn, tid, tpl, data.get('mec_date'))
        conn.commit()
    tx = dict(conn.execute("SELECT * FROM transactions WHERE id=?", (tid,)).fetchone())
    conn.close()
    return jsonify(tx), 201


@app.route('/api/transactions/<int:tid>', methods=['GET'])
def get_transaction(tid):
    conn = get_db()
    row  = conn.execute("SELECT * FROM transactions WHERE id=?", (tid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    tx = dict(row)
    tx['deadlines'] = [dict(d) for d in conn.execute(
        "SELECT * FROM deadlines WHERE transaction_id=? ORDER BY due_date, due_time", (tid,)
    ).fetchall()]
    # Attach share tokens
    tx['share_tokens'] = [dict(s) for s in conn.execute(
        "SELECT * FROM share_tokens WHERE transaction_id=? ORDER BY created_at DESC", (tid,)
    ).fetchall()]
    conn.close()
    return jsonify(tx)


@app.route('/api/transactions/<int:tid>', methods=['PUT'])
def update_transaction(tid):
    data = request.json or {}
    conn = get_db()
    conn.execute('''
        UPDATE transactions SET
          address=?, city=?, state=?, zip_code=?, mls_number=?, type=?, status=?,
          mec_date=?, closing_date=?, possession_date=?, purchase_price=?, earnest_money=?,
          client_name=?, client_phone=?, client_email=?,
          agent_name=?, co_agent=?,
          lender_name=?, lender_phone=?, lender_email=?,
          title_company=?, title_contact=?, title_phone=?,
          other_agent_name=?, other_agent_phone=?, tc_name=?, tc_email=?,
          hoa_name=?, notes=?, updated_at=datetime('now')
        WHERE id=?
    ''', _tx_params(data) + (tid,))
    conn.commit()
    tx = dict(conn.execute("SELECT * FROM transactions WHERE id=?", (tid,)).fetchone())
    conn.close()
    return jsonify(tx)


@app.route('/api/transactions/<int:tid>', methods=['DELETE'])
def delete_transaction(tid):
    conn = get_db()
    conn.execute("DELETE FROM transactions WHERE id=?", (tid,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


def _tx_params(data):
    return (
        data.get('address'), data.get('city'), data.get('state', 'CO'), data.get('zip_code'),
        data.get('mls_number'), data.get('type', 'buyer'), data.get('status', 'active'),
        data.get('mec_date'), data.get('closing_date'), data.get('possession_date'),
        data.get('purchase_price'), data.get('earnest_money'),
        data.get('client_name'), data.get('client_phone'), data.get('client_email'),
        data.get('agent_name'), data.get('co_agent'),
        data.get('lender_name'), data.get('lender_phone'), data.get('lender_email'),
        data.get('title_company'), data.get('title_contact'), data.get('title_phone'),
        data.get('other_agent_name'), data.get('other_agent_phone'),
        data.get('tc_name'), data.get('tc_email'),
        data.get('hoa_name'), data.get('notes'),
    )


# ---------------------------------------------------------------------------
# Routes — deadlines CRUD
# ---------------------------------------------------------------------------

@app.route('/api/transactions/<int:tid>/deadlines', methods=['POST'])
def create_deadline(tid):
    data = request.json or {}
    conn = get_db()
    cur  = conn.execute('''
        INSERT INTO deadlines
          (transaction_id, cbs_key, title, description, due_date, due_time,
           status, category, priority, notes)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    ''', (tid, data.get('cbs_key'), data.get('title'), data.get('description'),
          data.get('due_date'), data.get('due_time', '17:00'),
          data.get('status', 'pending'), data.get('category', 'custom'),
          data.get('priority', 'medium'), data.get('notes')))
    did = cur.lastrowid
    conn.commit()
    d = dict(conn.execute("SELECT * FROM deadlines WHERE id=?", (did,)).fetchone())
    conn.close()
    return jsonify(d), 201


@app.route('/api/deadlines/<int:did>', methods=['PUT'])
def update_deadline(did):
    data = request.json or {}
    conn = get_db()
    existing = conn.execute("SELECT * FROM deadlines WHERE id=?", (did,)).fetchone()
    if not existing:
        return jsonify({'error': 'Not found'}), 404
    completed_at = existing['completed_at']
    if data.get('status') == 'completed' and not completed_at:
        completed_at = datetime.now().isoformat()
    elif data.get('status') != 'completed':
        completed_at = None
    conn.execute('''
        UPDATE deadlines SET
          title=?, description=?, due_date=?, due_time=?,
          status=?, category=?, priority=?, notes=?,
          completed_at=?, completed_by=?, updated_at=datetime('now')
        WHERE id=?
    ''', (data.get('title'), data.get('description'), data.get('due_date'),
          data.get('due_time', '17:00'), data.get('status'), data.get('category'),
          data.get('priority'), data.get('notes'),
          completed_at, data.get('completed_by'), did))
    conn.commit()
    d = dict(conn.execute("SELECT * FROM deadlines WHERE id=?", (did,)).fetchone())
    conn.close()
    return jsonify(d)


@app.route('/api/deadlines/<int:did>/status', methods=['POST'])
def set_deadline_status(did):
    data     = request.json or {}
    status   = data.get('status')
    conn     = get_db()
    completed_at = datetime.now().isoformat() if status == 'completed' else None
    conn.execute(
        "UPDATE deadlines SET status=?, completed_at=?, completed_by=?, updated_at=datetime('now') WHERE id=?",
        (status, completed_at, data.get('completed_by', ''), did)
    )
    conn.commit()
    d = dict(conn.execute("SELECT * FROM deadlines WHERE id=?", (did,)).fetchone())
    conn.close()
    return jsonify(d)


@app.route('/api/deadlines/<int:did>', methods=['DELETE'])
def delete_deadline(did):
    conn = get_db()
    conn.execute("DELETE FROM deadlines WHERE id=?", (did,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ---------------------------------------------------------------------------
# Routes — CO CBS import (bulk create deadlines from contract dates)
# ---------------------------------------------------------------------------

@app.route('/api/transactions/<int:tid>/import-cbs', methods=['POST'])
def import_cbs(tid):
    """
    Accepts a list of {key, title, due_date, due_time, category, priority, description, enabled}
    and bulk-inserts all enabled entries as deadlines on the transaction.
    """
    items = request.json or []
    conn  = get_db()
    added = 0
    for item in items:
        if not item.get('enabled') or not item.get('due_date'):
            continue
        conn.execute('''
            INSERT INTO deadlines
              (transaction_id, cbs_key, title, description, due_date, due_time,
               status, category, priority)
            VALUES (?,?,?,?,?,?,\'pending\',?,?)
        ''', (tid, item.get('key'), item.get('title'), item.get('description', ''),
              item['due_date'], item.get('due_time', '17:00'),
              item.get('category', 'custom'), item.get('priority', 'medium')))
        added += 1
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'added': added})


# ---------------------------------------------------------------------------
# Routes — templates
# ---------------------------------------------------------------------------

@app.route('/api/templates', methods=['GET'])
def get_templates():
    return jsonify({
        k: {'name': v['name'], 'type': v['type'], 'count': len(v['deadlines'])}
        for k, v in DEADLINE_TEMPLATES.items()
    })


@app.route('/api/cbs-deadlines', methods=['GET'])
def get_cbs_deadlines():
    """Return the full CO CBS deadline definitions for the import form."""
    return jsonify(CO_CBS_DEADLINES)


@app.route('/api/transactions/<int:tid>/apply-template', methods=['POST'])
def apply_template_route(tid):
    data = request.json or {}
    key  = data.get('template')
    if key not in DEADLINE_TEMPLATES:
        return jsonify({'error': 'Unknown template'}), 400
    conn = get_db()
    mec  = data.get('mec_date')
    if not mec:
        row  = conn.execute("SELECT mec_date FROM transactions WHERE id=?", (tid,)).fetchone()
        mec  = row['mec_date'] if row else None
    count = _apply_template(conn, tid, key, mec)
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'added': count})


def _apply_template(conn, tid, key, mec_date):
    tpl  = DEADLINE_TEMPLATES[key]
    base = date.fromisoformat(mec_date) if mec_date else date.today()
    for item in tpl['deadlines']:
        days = item.get('default_days')
        if days is None:
            continue
        due = (base + timedelta(days=days)).isoformat()
        conn.execute('''
            INSERT INTO deadlines
              (transaction_id, cbs_key, title, description, due_date, due_time,
               status, category, priority)
            VALUES (?,?,?,?,?,'17:00','pending',?,?)
        ''', (tid, item['key'], item['title'], item.get('description', ''),
              due, item['category'], item['priority']))
    return len(tpl['deadlines'])


# ---------------------------------------------------------------------------
# Routes — share links
# ---------------------------------------------------------------------------

@app.route('/api/transactions/<int:tid>/share', methods=['POST'])
def create_share(tid):
    data  = request.json or {}
    token = secrets.token_urlsafe(24)
    conn  = get_db()
    conn.execute(
        "INSERT INTO share_tokens (token, transaction_id, label) VALUES (?,?,?)",
        (token, tid, data.get('label', ''))
    )
    conn.commit()
    conn.close()
    return jsonify({'token': token})


@app.route('/api/share-tokens/<token>', methods=['DELETE'])
def revoke_share(token):
    conn = get_db()
    conn.execute("DELETE FROM share_tokens WHERE token=?", (token,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ---------------------------------------------------------------------------
# Routes — settings
# ---------------------------------------------------------------------------

@app.route('/api/settings', methods=['GET'])
def get_settings():
    keys = ['notify_email', 'smtp_host', 'smtp_port', 'smtp_user',
            'notify_lead_days', 'notify_hour', 'notify_enabled', 'from_email']
    return jsonify({k: get_setting(k, '') for k in keys})


@app.route('/api/settings', methods=['POST'])
def save_settings():
    data = request.json or {}
    for k, v in data.items():
        set_setting(k, str(v))
    return jsonify({'success': True})


@app.route('/api/settings/test-email', methods=['POST'])
def test_email():
    ok, msg = send_email(
        'RE Deadline Tracker — Test Email',
        '<h2>It works!</h2><p>Your email notifications are configured correctly.</p>'
    )
    return jsonify({'success': ok, 'message': msg})


# ---------------------------------------------------------------------------
# Routes — reports
# ---------------------------------------------------------------------------

@app.route('/api/reports/summary', methods=['GET'])
def reports_summary():
    conn  = get_db()
    today = date.today().isoformat()
    year_start = f'{date.today().year}-01-01'

    rows = conn.execute("SELECT * FROM transactions ORDER BY created_at DESC").fetchall()
    txs  = [dict(r) for r in rows]

    # Compute stats per transaction
    for t in txs:
        t['total_deadlines']     = conn.execute("SELECT COUNT(*) FROM deadlines WHERE transaction_id=?", (t['id'],)).fetchone()[0]
        t['completed_deadlines'] = conn.execute("SELECT COUNT(*) FROM deadlines WHERE transaction_id=? AND status='completed'", (t['id'],)).fetchone()[0]
        t['pending_deadlines']   = conn.execute("SELECT COUNT(*) FROM deadlines WHERE transaction_id=? AND status='pending'", (t['id'],)).fetchone()[0]

    active    = [t for t in txs if t['status'] in ('active', 'under_contract')]
    closed    = [t for t in txs if t['status'] == 'closed']
    ytd_closed = [t for t in closed if t.get('closing_date', '') >= year_start]

    pipeline_value = sum((t.get('purchase_price') or 0) for t in active)
    ytd_volume     = sum((t.get('purchase_price') or 0) for t in ytd_closed)

    conn.close()
    return jsonify({
        'active':         active,
        'closed':         closed,
        'ytd_closed':     ytd_closed,
        'pipeline_value': pipeline_value,
        'ytd_volume':     ytd_volume,
        'stats': {
            'active_count':     len(active),
            'closed_count':     len(closed),
            'ytd_closed_count': len(ytd_closed),
            'pipeline_value':   pipeline_value,
            'ytd_volume':       ytd_volume,
        }
    })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    init_db()
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        start_scheduler()
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=True, host='0.0.0.0', port=port)
