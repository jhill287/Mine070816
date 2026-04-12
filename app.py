"""
Real Estate Transaction Deadline Tracker
Flask backend with SQLite database
"""

from flask import Flask, render_template, request, jsonify
import sqlite3
import os
from datetime import datetime, date, timedelta

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), 'real_estate.db')

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS transactions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            address         TEXT    NOT NULL,
            city            TEXT,
            state           TEXT,
            zip_code        TEXT,
            mls_number      TEXT,
            type            TEXT    NOT NULL DEFAULT 'buyer',
            status          TEXT    NOT NULL DEFAULT 'active',
            contract_date   TEXT,
            closing_date    TEXT,
            purchase_price  REAL,
            client_name     TEXT,
            client_phone    TEXT,
            client_email    TEXT,
            agent_name      TEXT,
            co_agent        TEXT,
            lender_name     TEXT,
            lender_phone    TEXT,
            title_company   TEXT,
            title_contact   TEXT,
            notes           TEXT,
            created_at      TEXT    DEFAULT (datetime('now')),
            updated_at      TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS deadlines (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id  INTEGER NOT NULL,
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

        CREATE TABLE IF NOT EXISTS audit_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type     TEXT    NOT NULL,
            entity_id       INTEGER NOT NULL,
            action          TEXT    NOT NULL,
            old_value       TEXT,
            new_value       TEXT,
            created_at      TEXT    DEFAULT (datetime('now'))
        );
    ''')
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Deadline templates  (days are relative to contract_date)
# ---------------------------------------------------------------------------

DEADLINE_TEMPLATES = {
    'standard_buyer_30': {
        'name': 'Buyer — Standard 30-Day Close',
        'type': 'buyer',
        'deadlines': [
            {'title': 'Earnest Money Delivered',        'days': 3,  'category': 'earnest_money', 'priority': 'high',   'description': 'Deliver earnest money check/wire to title company'},
            {'title': 'Option Period Begins',           'days': 0,  'category': 'inspection',    'priority': 'medium', 'description': 'Option/due-diligence period starts — schedule inspections immediately'},
            {'title': 'General Inspection',             'days': 5,  'category': 'inspection',    'priority': 'high',   'description': 'Complete general home inspection'},
            {'title': 'Specialty Inspections Due',      'days': 7,  'category': 'inspection',    'priority': 'medium', 'description': 'Sewer scope, roof, HVAC, pest, pool, etc.'},
            {'title': 'Option / Inspection Deadline',   'days': 10, 'category': 'inspection',    'priority': 'high',   'description': 'Last day to terminate under option or submit inspection objections'},
            {'title': 'Inspection Resolution Deadline', 'days': 15, 'category': 'inspection',    'priority': 'high',   'description': 'Seller responds to repair requests — agree on credits/repairs'},
            {'title': 'Loan Application Submitted',     'days': 3,  'category': 'financing',     'priority': 'high',   'description': 'Formal loan application submitted to lender'},
            {'title': 'Loan Estimate Reviewed',         'days': 5,  'category': 'financing',     'priority': 'medium', 'description': 'Review and sign Loan Estimate from lender'},
            {'title': 'Appraisal Ordered',              'days': 7,  'category': 'appraisal',     'priority': 'medium', 'description': 'Lender orders appraisal of property'},
            {'title': 'Appraisal Completed',            'days': 21, 'category': 'appraisal',     'priority': 'high',   'description': 'Appraisal must be completed and results reviewed'},
            {'title': 'Appraisal Objection Deadline',   'days': 23, 'category': 'appraisal',     'priority': 'high',   'description': 'Notify seller if appraisal came in low'},
            {'title': 'HOA Documents Requested',        'days': 5,  'category': 'hoa',           'priority': 'medium', 'description': 'Request HOA resale certificate / docs from seller or HOA'},
            {'title': 'HOA Document Review Deadline',   'days': 20, 'category': 'hoa',           'priority': 'high',   'description': 'Review HOA docs — can terminate if financially unsatisfactory'},
            {'title': 'Survey Ordered',                 'days': 5,  'category': 'survey',        'priority': 'medium', 'description': 'Order survey of property (if required)'},
            {'title': 'Survey Review Deadline',         'days': 18, 'category': 'survey',        'priority': 'high',   'description': 'Review survey for encroachments/easements'},
            {'title': 'Title Commitment Received',      'days': 12, 'category': 'title',         'priority': 'medium', 'description': 'Receive title commitment from title company'},
            {'title': 'Title Review Deadline',          'days': 17, 'category': 'title',         'priority': 'high',   'description': 'Review title commitment — object to any defects'},
            {'title': 'Homeowners Insurance Bound',     'days': 20, 'category': 'insurance',     'priority': 'high',   'description': 'Obtain and bind homeowners insurance policy'},
            {'title': 'Financing / Loan Approval',      'days': 25, 'category': 'financing',     'priority': 'high',   'description': 'Receive final loan approval / Clear to Close from lender'},
            {'title': 'Financing Contingency Deadline', 'days': 25, 'category': 'financing',     'priority': 'high',   'description': 'Must waive or exercise financing contingency by this date'},
            {'title': 'Closing Disclosure Reviewed',    'days': 27, 'category': 'closing',       'priority': 'high',   'description': 'Review final Closing Disclosure (required 3 business days prior)'},
            {'title': 'Wire Closing Funds',             'days': 29, 'category': 'closing',       'priority': 'high',   'description': 'Wire down payment and closing costs to title company'},
            {'title': 'Final Walkthrough',              'days': 29, 'category': 'walkthrough',   'priority': 'medium', 'description': 'Final walkthrough to verify property condition'},
            {'title': 'CLOSING / SETTLEMENT',           'days': 30, 'category': 'closing',       'priority': 'high',   'description': 'Sign closing documents and receive keys'},
        ]
    },
    'standard_seller_30': {
        'name': 'Seller — Standard 30-Day Close',
        'type': 'seller',
        'deadlines': [
            {'title': 'Signed Disclosures Delivered',   'days': 2,  'category': 'disclosure',    'priority': 'high',   'description': 'Complete and deliver all required seller disclosures to buyer'},
            {'title': 'MLS Photos / Marketing Ready',   'days': 2,  'category': 'custom',        'priority': 'medium', 'description': 'Professional photos taken, listing copy written'},
            {'title': 'Property Active on MLS',         'days': 3,  'category': 'custom',        'priority': 'high',   'description': 'Listing goes live on MLS and syndication sites'},
            {'title': 'Confirm Earnest Money Received', 'days': 4,  'category': 'earnest_money', 'priority': 'high',   'description': 'Verify buyer delivered earnest money to title company'},
            {'title': 'Option Period Expires',          'days': 10, 'category': 'inspection',    'priority': 'high',   'description': 'Buyer option / due-diligence period ends today'},
            {'title': 'Respond to Inspection Requests', 'days': 13, 'category': 'inspection',    'priority': 'high',   'description': 'Respond to buyer inspection repair requests / counter-offer'},
            {'title': 'Confirm Buyer Financing Status', 'days': 18, 'category': 'financing',     'priority': 'medium', 'description': 'Check with listing agent on buyer loan progress'},
            {'title': 'Order Repair Work',              'days': 16, 'category': 'inspection',    'priority': 'medium', 'description': 'Schedule and begin any agreed-upon repair work'},
            {'title': 'Repair Work Completed',          'days': 25, 'category': 'inspection',    'priority': 'high',   'description': 'All agreed repairs completed — save receipts for buyer'},
            {'title': 'Confirm Loan Approval',          'days': 26, 'category': 'financing',     'priority': 'high',   'description': 'Confirm buyer has received clear to close'},
            {'title': 'Utilities Scheduling',           'days': 25, 'category': 'custom',        'priority': 'medium', 'description': 'Schedule utility transfers / cancellations for closing date'},
            {'title': 'Moving Company Booked',          'days': 14, 'category': 'custom',        'priority': 'medium', 'description': 'Confirm moving company is scheduled'},
            {'title': 'Vacate Property',                'days': 29, 'category': 'closing',       'priority': 'high',   'description': 'Remove all belongings — property must be in agreed condition'},
            {'title': 'Final Walkthrough by Buyer',     'days': 29, 'category': 'walkthrough',   'priority': 'medium', 'description': 'Accommodate buyer final walkthrough — ensure property is ready'},
            {'title': 'CLOSING / SETTLEMENT',           'days': 30, 'category': 'closing',       'priority': 'high',   'description': 'Sign closing documents, transfer ownership, receive proceeds'},
        ]
    },
    'standard_buyer_45': {
        'name': 'Buyer — 45-Day Close',
        'type': 'buyer',
        'deadlines': [
            {'title': 'Earnest Money Delivered',        'days': 3,  'category': 'earnest_money', 'priority': 'high',   'description': 'Deliver earnest money to title company'},
            {'title': 'Option / Inspection Deadline',   'days': 14, 'category': 'inspection',    'priority': 'high',   'description': 'Last day to terminate under option or submit inspection objections'},
            {'title': 'Inspection Resolution Deadline', 'days': 20, 'category': 'inspection',    'priority': 'high',   'description': 'Agree on inspection repairs or credits'},
            {'title': 'Loan Application Submitted',     'days': 3,  'category': 'financing',     'priority': 'high',   'description': 'Submit formal loan application'},
            {'title': 'Appraisal Completed',            'days': 28, 'category': 'appraisal',     'priority': 'high',   'description': 'Appraisal must be completed'},
            {'title': 'HOA Document Review Deadline',   'days': 28, 'category': 'hoa',           'priority': 'high',   'description': 'Review HOA docs'},
            {'title': 'Title Review Deadline',          'days': 25, 'category': 'title',         'priority': 'high',   'description': 'Review title commitment'},
            {'title': 'Homeowners Insurance Bound',     'days': 30, 'category': 'insurance',     'priority': 'high',   'description': 'Obtain homeowners insurance'},
            {'title': 'Financing / Loan Approval',      'days': 38, 'category': 'financing',     'priority': 'high',   'description': 'Receive final loan approval / Clear to Close'},
            {'title': 'Closing Disclosure Reviewed',    'days': 42, 'category': 'closing',       'priority': 'high',   'description': 'Review final Closing Disclosure'},
            {'title': 'Wire Closing Funds',             'days': 44, 'category': 'closing',       'priority': 'high',   'description': 'Wire down payment and closing costs'},
            {'title': 'Final Walkthrough',              'days': 44, 'category': 'walkthrough',   'priority': 'medium', 'description': 'Final walkthrough of property'},
            {'title': 'CLOSING / SETTLEMENT',           'days': 45, 'category': 'closing',       'priority': 'high',   'description': 'Sign closing documents and receive keys'},
        ]
    },
    'lease': {
        'name': 'Lease Transaction',
        'type': 'lease',
        'deadlines': [
            {'title': 'Rental Application Submitted',   'days': 1,  'category': 'custom',        'priority': 'high',   'description': 'Tenant submits completed rental application'},
            {'title': 'Background / Credit Check',      'days': 2,  'category': 'custom',        'priority': 'high',   'description': 'Complete tenant screening — credit, background, income verification'},
            {'title': 'Application Decision',           'days': 3,  'category': 'custom',        'priority': 'high',   'description': 'Approve or deny application — notify tenant'},
            {'title': 'Lease Agreement Signed',         'days': 5,  'category': 'custom',        'priority': 'high',   'description': 'All parties sign lease agreement'},
            {'title': 'Security Deposit Collected',     'days': 5,  'category': 'earnest_money', 'priority': 'high',   'description': 'Collect security deposit from tenant'},
            {'title': 'First Month Rent Collected',     'days': 5,  'category': 'earnest_money', 'priority': 'high',   'description': 'Collect first month rent (and last if applicable)'},
            {'title': 'Renters Insurance Required',     'days': 6,  'category': 'insurance',     'priority': 'medium', 'description': 'Tenant provides proof of renters insurance (if required)'},
            {'title': 'Move-In Inspection / Key Handover', 'days': 7, 'category': 'closing',    'priority': 'high',   'description': 'Complete move-in inspection form, document condition, hand over keys'},
        ]
    },
    'refinance': {
        'name': 'Refinance',
        'type': 'buyer',
        'deadlines': [
            {'title': 'Loan Application Submitted',     'days': 1,  'category': 'financing',     'priority': 'high',   'description': 'Submit refinance loan application to lender'},
            {'title': 'Loan Estimate Reviewed',         'days': 3,  'category': 'financing',     'priority': 'high',   'description': 'Review and sign Loan Estimate'},
            {'title': 'Documents Submitted to Lender',  'days': 5,  'category': 'financing',     'priority': 'high',   'description': 'Provide income docs, bank statements, tax returns to lender'},
            {'title': 'Appraisal Ordered / Completed',  'days': 14, 'category': 'appraisal',     'priority': 'high',   'description': 'Lender orders and receives appraisal'},
            {'title': 'Title Search Ordered',           'days': 7,  'category': 'title',         'priority': 'medium', 'description': 'Title company performs title search'},
            {'title': 'Underwriting Approval',          'days': 25, 'category': 'financing',     'priority': 'high',   'description': 'File clears underwriting — receive conditional or final approval'},
            {'title': 'Clear to Close',                 'days': 28, 'category': 'financing',     'priority': 'high',   'description': 'All conditions satisfied — receive Clear to Close'},
            {'title': 'Closing Disclosure Reviewed',    'days': 29, 'category': 'closing',       'priority': 'high',   'description': 'Review Closing Disclosure (3 day waiting period required)'},
            {'title': 'Right of Rescission Period',     'days': 32, 'category': 'closing',       'priority': 'high',   'description': 'Three-day right of rescission period for primary residence refi'},
            {'title': 'Funds Disbursed',                'days': 33, 'category': 'closing',       'priority': 'high',   'description': 'Loan funds disbursed, old loan paid off'},
        ]
    }
}


# ---------------------------------------------------------------------------
# API — Dashboard / Alerts
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/dashboard')
def dashboard():
    conn = get_db()
    today = date.today().isoformat()
    week_out = (date.today() + timedelta(days=7)).isoformat()

    stats = {
        'total_active': conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE status IN ('active','under_contract')"
        ).fetchone()[0],
        'overdue': conn.execute(
            "SELECT COUNT(*) FROM deadlines d JOIN transactions t ON d.transaction_id=t.id "
            "WHERE d.status='pending' AND d.due_date < ? AND t.status IN ('active','under_contract')",
            (today,)
        ).fetchone()[0],
        'due_today': conn.execute(
            "SELECT COUNT(*) FROM deadlines d JOIN transactions t ON d.transaction_id=t.id "
            "WHERE d.status='pending' AND d.due_date = ? AND t.status IN ('active','under_contract')",
            (today,)
        ).fetchone()[0],
        'due_this_week': conn.execute(
            "SELECT COUNT(*) FROM deadlines d JOIN transactions t ON d.transaction_id=t.id "
            "WHERE d.status='pending' AND d.due_date > ? AND d.due_date <= ? "
            "AND t.status IN ('active','under_contract')",
            (today, week_out)
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
    today = date.today().isoformat()
    three_days = (date.today() + timedelta(days=3)).isoformat()

    overdue = conn.execute(
        "SELECT d.*, t.address, t.client_name, t.type as trans_type "
        "FROM deadlines d JOIN transactions t ON d.transaction_id=t.id "
        "WHERE d.status='pending' AND d.due_date < ? "
        "AND t.status IN ('active','under_contract') "
        "ORDER BY d.due_date ASC", (today,)
    ).fetchall()

    due_soon = conn.execute(
        "SELECT d.*, t.address, t.client_name, t.type as trans_type "
        "FROM deadlines d JOIN transactions t ON d.transaction_id=t.id "
        "WHERE d.status='pending' AND d.due_date >= ? AND d.due_date <= ? "
        "AND t.status IN ('active','under_contract') "
        "ORDER BY d.due_date ASC", (today, three_days)
    ).fetchall()

    conn.close()
    return jsonify({
        'overdue': [dict(r) for r in overdue],
        'due_soon': [dict(r) for r in due_soon]
    })


# ---------------------------------------------------------------------------
# API — Transactions
# ---------------------------------------------------------------------------

@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    conn = get_db()
    today = date.today().isoformat()

    status_filter = request.args.get('status', '')
    search = request.args.get('search', '')

    query = "SELECT * FROM transactions WHERE 1=1"
    params = []

    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)

    if search:
        query += " AND (address LIKE ? OR client_name LIKE ? OR mls_number LIKE ?)"
        params.extend([f'%{search}%'] * 3)

    query += " ORDER BY CASE status WHEN 'active' THEN 1 WHEN 'under_contract' THEN 2 WHEN 'closed' THEN 3 ELSE 4 END, created_at DESC"

    transactions = [dict(t) for t in conn.execute(query, params).fetchall()]

    for t in transactions:
        rows = conn.execute(
            "SELECT * FROM deadlines WHERE transaction_id=? AND status='pending' ORDER BY due_date ASC",
            (t['id'],)
        ).fetchall()

        t['total_deadlines'] = conn.execute(
            "SELECT COUNT(*) FROM deadlines WHERE transaction_id=?", (t['id'],)
        ).fetchone()[0]

        t['pending_deadlines'] = len(rows)
        t['overdue_count'] = sum(1 for d in rows if d['due_date'] < today)

        # Next upcoming (not overdue); fall back to most-overdue
        upcoming = [d for d in rows if d['due_date'] >= today]
        t['next_deadline'] = dict(upcoming[0]) if upcoming else (dict(rows[0]) if rows else None)

    conn.close()
    return jsonify(transactions)


@app.route('/api/transactions', methods=['POST'])
def create_transaction():
    data = request.json or {}
    conn = get_db()

    cur = conn.execute('''
        INSERT INTO transactions
            (address, city, state, zip_code, mls_number, type, status,
             contract_date, closing_date, purchase_price,
             client_name, client_phone, client_email,
             agent_name, co_agent, lender_name, lender_phone,
             title_company, title_contact, notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ''', (
        data.get('address'), data.get('city'), data.get('state'), data.get('zip_code'),
        data.get('mls_number'), data.get('type', 'buyer'), data.get('status', 'active'),
        data.get('contract_date'), data.get('closing_date'), data.get('purchase_price'),
        data.get('client_name'), data.get('client_phone'), data.get('client_email'),
        data.get('agent_name'), data.get('co_agent'), data.get('lender_name'),
        data.get('lender_phone'), data.get('title_company'), data.get('title_contact'),
        data.get('notes')
    ))
    tid = cur.lastrowid
    conn.commit()

    template_key = data.get('template')
    if template_key and template_key in DEADLINE_TEMPLATES:
        _apply_template(conn, tid, template_key, data.get('contract_date'))
        conn.commit()

    transaction = dict(conn.execute("SELECT * FROM transactions WHERE id=?", (tid,)).fetchone())
    conn.close()
    return jsonify(transaction), 201


@app.route('/api/transactions/<int:tid>', methods=['GET'])
def get_transaction(tid):
    conn = get_db()
    row = conn.execute("SELECT * FROM transactions WHERE id=?", (tid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404

    t = dict(row)
    t['deadlines'] = [dict(d) for d in conn.execute(
        "SELECT * FROM deadlines WHERE transaction_id=? ORDER BY due_date ASC, due_time ASC", (tid,)
    ).fetchall()]

    conn.close()
    return jsonify(t)


@app.route('/api/transactions/<int:tid>', methods=['PUT'])
def update_transaction(tid):
    data = request.json or {}
    conn = get_db()

    conn.execute('''
        UPDATE transactions SET
            address=?, city=?, state=?, zip_code=?, mls_number=?, type=?, status=?,
            contract_date=?, closing_date=?, purchase_price=?,
            client_name=?, client_phone=?, client_email=?,
            agent_name=?, co_agent=?, lender_name=?, lender_phone=?,
            title_company=?, title_contact=?, notes=?,
            updated_at=datetime('now')
        WHERE id=?
    ''', (
        data.get('address'), data.get('city'), data.get('state'), data.get('zip_code'),
        data.get('mls_number'), data.get('type'), data.get('status'),
        data.get('contract_date'), data.get('closing_date'), data.get('purchase_price'),
        data.get('client_name'), data.get('client_phone'), data.get('client_email'),
        data.get('agent_name'), data.get('co_agent'), data.get('lender_name'),
        data.get('lender_phone'), data.get('title_company'), data.get('title_contact'),
        data.get('notes'), tid
    ))
    conn.commit()
    t = dict(conn.execute("SELECT * FROM transactions WHERE id=?", (tid,)).fetchone())
    conn.close()
    return jsonify(t)


@app.route('/api/transactions/<int:tid>', methods=['DELETE'])
def delete_transaction(tid):
    conn = get_db()
    conn.execute("DELETE FROM transactions WHERE id=?", (tid,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ---------------------------------------------------------------------------
# API — Deadlines
# ---------------------------------------------------------------------------

@app.route('/api/transactions/<int:tid>/deadlines', methods=['POST'])
def create_deadline(tid):
    data = request.json or {}
    conn = get_db()

    cur = conn.execute('''
        INSERT INTO deadlines
            (transaction_id, title, description, due_date, due_time,
             status, category, priority, notes)
        VALUES (?,?,?,?,?,?,?,?,?)
    ''', (
        tid, data.get('title'), data.get('description'),
        data.get('due_date'), data.get('due_time', '17:00'),
        data.get('status', 'pending'), data.get('category', 'custom'),
        data.get('priority', 'medium'), data.get('notes')
    ))
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
    ''', (
        data.get('title'), data.get('description'), data.get('due_date'),
        data.get('due_time', '17:00'), data.get('status'), data.get('category'),
        data.get('priority'), data.get('notes'),
        completed_at, data.get('completed_by'), did
    ))
    conn.commit()
    d = dict(conn.execute("SELECT * FROM deadlines WHERE id=?", (did,)).fetchone())
    conn.close()
    return jsonify(d)


@app.route('/api/deadlines/<int:did>/status', methods=['POST'])
def set_deadline_status(did):
    data = request.json or {}
    new_status = data.get('status')
    conn = get_db()

    completed_at = datetime.now().isoformat() if new_status == 'completed' else None

    conn.execute(
        "UPDATE deadlines SET status=?, completed_at=?, completed_by=?, updated_at=datetime('now') WHERE id=?",
        (new_status, completed_at, data.get('completed_by', ''), did)
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
# API — Templates
# ---------------------------------------------------------------------------

@app.route('/api/templates', methods=['GET'])
def get_templates():
    return jsonify({
        k: {'name': v['name'], 'type': v['type'], 'count': len(v['deadlines'])}
        for k, v in DEADLINE_TEMPLATES.items()
    })


@app.route('/api/transactions/<int:tid>/apply-template', methods=['POST'])
def apply_template_route(tid):
    data = request.json or {}
    key = data.get('template')
    if key not in DEADLINE_TEMPLATES:
        return jsonify({'error': 'Unknown template'}), 400

    conn = get_db()
    contract_date = data.get('contract_date')
    if not contract_date:
        row = conn.execute("SELECT contract_date FROM transactions WHERE id=?", (tid,)).fetchone()
        contract_date = row['contract_date'] if row else None

    count = _apply_template(conn, tid, key, contract_date)
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'added': count})


def _apply_template(conn, tid, key, contract_date):
    tpl = DEADLINE_TEMPLATES[key]
    base = date.fromisoformat(contract_date) if contract_date else date.today()
    for item in tpl['deadlines']:
        due = (base + timedelta(days=item['days'])).isoformat()
        conn.execute('''
            INSERT INTO deadlines
                (transaction_id, title, description, due_date, due_time, status, category, priority)
            VALUES (?,?,?,?,'17:00','pending',?,?)
        ''', (tid, item['title'], item.get('description', ''), due, item['category'], item['priority']))
    return len(tpl['deadlines'])


# ---------------------------------------------------------------------------

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
