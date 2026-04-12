'use strict';

// ─────────────────────────────────────────────── State ───
const S = {
  transactions: [],
  currentTx: null,   // full transaction object with deadlines
  templates: {},
};

// ─────────────────────────────────────────────── Boot ───
document.addEventListener('DOMContentLoaded', () => {
  loadTemplates();
  showDashboard();
});

// ─────────────────────────────────────────────── API helper ───
async function api(method, path, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(txt || `HTTP ${res.status}`);
  }
  return res.json();
}

// ─────────────────────────────────────────────── Views ───
function showDashboard() {
  document.getElementById('dashboardView').classList.remove('d-none');
  document.getElementById('transactionView').classList.add('d-none');
  loadDashboard();
  loadTransactions();
}

function showTransaction(tx) {
  S.currentTx = tx;
  document.getElementById('dashboardView').classList.add('d-none');
  document.getElementById('transactionView').classList.remove('d-none');
  renderTransactionDetail();
}

// ─────────────────────────────────────────────── Dashboard ───
async function loadDashboard() {
  try {
    const [stats, alertData] = await Promise.all([
      api('GET', '/api/dashboard'),
      api('GET', '/api/alerts'),
    ]);

    document.getElementById('statActive').textContent  = stats.total_active;
    document.getElementById('statOverdue').textContent = stats.overdue;
    document.getElementById('statToday').textContent   = stats.due_today;
    document.getElementById('statWeek').textContent    = stats.due_this_week;

    // Alert bell
    const urgentCount = stats.overdue + stats.due_today;
    const bell = document.getElementById('alertBell');
    if (urgentCount > 0) {
      bell.classList.remove('d-none');
      document.getElementById('alertBellCount').textContent = urgentCount;
    } else {
      bell.classList.add('d-none');
    }

    renderAlerts(alertData);
  } catch (e) { console.error(e); }
}

function renderAlerts({ overdue, due_soon }) {
  const el = document.getElementById('alertsSection');
  let html = '';

  if (overdue.length) {
    html += `<div class="alert alert-danger alert-dismissible fade show mb-3" id="alertsAnchor">
      <strong><i class="fa-solid fa-circle-exclamation me-2"></i>${overdue.length} Overdue Deadline${overdue.length > 1 ? 's' : ''}</strong>
      <ul class="mb-0 mt-1">`;
    overdue.forEach(d => {
      html += `<li>
        <a href="#" class="alert-link" onclick="openTransactionById(${d.transaction_id})">
          ${esc(d.address)}
        </a> — <strong>${esc(d.title)}</strong>
        <span class="badge bg-danger ms-1">${daysLabel(d.due_date)}</span>
      </li>`;
    });
    html += `</ul><button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>`;
  }

  if (due_soon.length) {
    html += `<div class="alert alert-warning alert-dismissible fade show mb-3">
      <strong><i class="fa-solid fa-clock me-2"></i>${due_soon.length} Deadline${due_soon.length > 1 ? 's' : ''} Due Within 3 Days</strong>
      <ul class="mb-0 mt-1">`;
    due_soon.forEach(d => {
      html += `<li>
        <a href="#" class="alert-link" onclick="openTransactionById(${d.transaction_id})">
          ${esc(d.address)}
        </a> — <strong>${esc(d.title)}</strong>
        <span class="badge bg-warning text-dark ms-1">${daysLabel(d.due_date)}</span>
      </li>`;
    });
    html += `</ul><button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>`;
  }

  el.innerHTML = html;
}

function scrollToAlerts() {
  const el = document.getElementById('alertsAnchor');
  if (el) el.scrollIntoView({ behavior: 'smooth' });
}

// ─────────────────────────────────────────────── Transaction List ───
async function loadTransactions() {
  try {
    const status = document.querySelector('input[name="statusFilter"]:checked')?.value || '';
    const search = document.getElementById('searchInput')?.value || '';
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    if (search) params.set('search', search);
    S.transactions = await api('GET', `/api/transactions?${params}`);
    renderTransactionGrid();
  } catch (e) { console.error(e); }
}

function filterTransactions() { loadTransactions(); }

function renderTransactionGrid() {
  const grid  = document.getElementById('transactionGrid');
  const empty = document.getElementById('emptyState');
  const count = document.getElementById('txCount');

  count.textContent = `${S.transactions.length} transaction${S.transactions.length !== 1 ? 's' : ''}`;

  if (!S.transactions.length) {
    grid.innerHTML = '';
    empty.classList.remove('d-none');
    return;
  }
  empty.classList.add('d-none');

  grid.innerHTML = S.transactions.map(t => txCard(t)).join('');
}

function txCard(t) {
  const statusClass = txStatusClass(t.status);
  const statusLabel = txStatusLabel(t.status);
  const typeIcon    = txTypeIcon(t.type);

  let urgencyHtml = '';
  if (t.overdue_count > 0) {
    urgencyHtml = `<span class="badge bg-danger"><i class="fa-solid fa-circle-exclamation me-1"></i>${t.overdue_count} Overdue</span>`;
  } else if (t.pending_deadlines > 0 && t.next_deadline) {
    const days = daysUntil(t.next_deadline.due_date);
    if (days === 0) {
      urgencyHtml = `<span class="badge bg-warning text-dark">Due today</span>`;
    } else if (days <= 3) {
      urgencyHtml = `<span class="badge bg-warning text-dark">${days}d left</span>`;
    }
  }

  const nextDl = t.next_deadline
    ? `<div class="tx-next-deadline">
        ${catIcon(t.next_deadline.category)}
        <span>${esc(t.next_deadline.title)}</span>
        <span class="ms-auto ${urgencyClass(t.next_deadline.due_date, t.next_deadline.status)}">${formatDate(t.next_deadline.due_date)}</span>
       </div>`
    : `<div class="tx-next-deadline text-muted"><i class="fa-regular fa-circle-check me-1"></i>No pending deadlines</div>`;

  const price = t.purchase_price ? `$${Number(t.purchase_price).toLocaleString()}` : '';

  return `
  <div class="col-12 col-md-6 col-xl-4">
    <div class="tx-card ${t.overdue_count > 0 ? 'tx-card-overdue' : ''}" onclick="openTransactionById(${t.id})">
      <div class="tx-card-header">
        <div class="d-flex align-items-start gap-2 flex-grow-1 min-w-0">
          <span class="tx-type-icon">${typeIcon}</span>
          <div class="min-w-0">
            <div class="tx-address">${esc(t.address)}${t.city ? ', ' + esc(t.city) : ''}</div>
            <div class="tx-client">${t.client_name ? esc(t.client_name) : '<span class="text-muted">No client</span>'}</div>
          </div>
        </div>
        <div class="d-flex flex-column align-items-end gap-1 flex-shrink-0">
          <span class="badge ${statusClass}">${statusLabel}</span>
          ${urgencyHtml}
        </div>
      </div>
      <div class="tx-card-body">
        <div class="tx-meta">
          ${price ? `<span><i class="fa-solid fa-dollar-sign text-muted me-1"></i>${price}</span>` : ''}
          ${t.closing_date ? `<span><i class="fa-regular fa-calendar text-muted me-1"></i>Close ${formatDate(t.closing_date)}</span>` : ''}
          ${t.mls_number ? `<span class="text-muted">MLS #${esc(t.mls_number)}</span>` : ''}
        </div>
        <div class="tx-deadline-summary">
          <span class="${t.overdue_count > 0 ? 'text-danger fw-semibold' : 'text-muted'}">
            <i class="fa-regular fa-clock me-1"></i>${t.pending_deadlines} pending
          </span>
          <span class="text-muted">· ${t.total_deadlines} total</span>
        </div>
        ${nextDl}
      </div>
    </div>
  </div>`;
}

async function openTransactionById(id) {
  try {
    const tx = await api('GET', `/api/transactions/${id}`);
    showTransaction(tx);
  } catch (e) { console.error(e); }
}

// ─────────────────────────────────────────────── Transaction Detail ───
function renderTransactionDetail() {
  const tx = S.currentTx;
  document.getElementById('txViewTitle').textContent = tx.address + (tx.city ? ', ' + tx.city : '');

  // Info card
  const price = tx.purchase_price ? `$${Number(tx.purchase_price).toLocaleString()}` : '—';
  const rows = [
    ['Type',         txTypeLabel(tx.type)],
    ['Status',       `<span class="badge ${txStatusClass(tx.status)}">${txStatusLabel(tx.status)}</span>`],
    ['Price',        price],
    ['MLS #',        tx.mls_number || '—'],
    ['Contract',     tx.contract_date ? formatDate(tx.contract_date) : '—'],
    ['Closing',      tx.closing_date  ? `<strong>${formatDate(tx.closing_date)}</strong>` : '—'],
    ['Client',       tx.client_name  || '—'],
    ['Client Phone', tx.client_phone  ? `<a href="tel:${tx.client_phone}">${esc(tx.client_phone)}</a>` : '—'],
    ['Client Email', tx.client_email  ? `<a href="mailto:${tx.client_email}">${esc(tx.client_email)}</a>` : '—'],
    ['Agent',        tx.agent_name   || '—'],
    ['Co-Agent',     tx.co_agent     || '—'],
    ['Lender',       tx.lender_name  || '—'],
    ['Lender Phone', tx.lender_phone  ? `<a href="tel:${tx.lender_phone}">${esc(tx.lender_phone)}</a>` : '—'],
    ['Title Co.',    tx.title_company || '—'],
    ['Title Contact',tx.title_contact || '—'],
  ].filter(([, v]) => v !== '—' || true);

  document.getElementById('txInfoCard').innerHTML = `
    <div class="row g-0">
      ${rows.map(([label, val]) => `
        <div class="col-6 col-md-4 col-lg-3">
          <div class="info-cell">
            <div class="info-label">${label}</div>
            <div class="info-val">${val}</div>
          </div>
        </div>`).join('')}
      ${tx.notes ? `
        <div class="col-12">
          <div class="info-cell">
            <div class="info-label">Notes</div>
            <div class="info-val">${esc(tx.notes)}</div>
          </div>
        </div>` : ''}
    </div>`;

  // Pre-fill template modal contract date
  document.getElementById('tplContractDate').value = tx.contract_date || '';
  renderDeadlines();
}

function renderDeadlines() {
  const tx = S.currentTx;
  const filter = document.querySelector('input[name="dlFilter"]:checked')?.value || 'all';
  const list  = document.getElementById('deadlineList');
  const empty = document.getElementById('deadlineEmpty');

  let deadlines = [...(tx.deadlines || [])];

  if (filter === 'pending') deadlines = deadlines.filter(d => d.status === 'pending');
  if (filter === 'done')    deadlines = deadlines.filter(d => d.status !== 'pending');

  if (!deadlines.length) {
    list.innerHTML = '';
    empty.classList.remove('d-none');
    return;
  }
  empty.classList.add('d-none');

  // Group by status bucket: overdue → today → upcoming → done
  const today = todayStr();
  const groups = { overdue: [], today: [], upcoming: [], done: [] };
  deadlines.forEach(d => {
    if (d.status !== 'pending') { groups.done.push(d); return; }
    if (d.due_date < today)     { groups.overdue.push(d); return; }
    if (d.due_date === today)   { groups.today.push(d); return; }
    groups.upcoming.push(d);
  });

  let html = '';
  if (groups.overdue.length)  html += dlGroup('Overdue', groups.overdue, 'overdue');
  if (groups.today.length)    html += dlGroup('Due Today', groups.today, 'today');
  if (groups.upcoming.length) html += dlGroup('Upcoming', groups.upcoming, 'upcoming');
  if (groups.done.length)     html += dlGroup('Completed / Closed', groups.done, 'done');

  list.innerHTML = html;
}

function dlGroup(title, deadlines, bucket) {
  const iconMap = {
    overdue:  '<i class="fa-solid fa-circle-exclamation text-danger me-2"></i>',
    today:    '<i class="fa-solid fa-calendar-day text-warning me-2"></i>',
    upcoming: '<i class="fa-regular fa-calendar text-info me-2"></i>',
    done:     '<i class="fa-regular fa-circle-check text-success me-2"></i>',
  };
  return `
    <div class="dl-group mb-4">
      <div class="dl-group-header">${iconMap[bucket]}${title} <span class="badge bg-secondary ms-1">${deadlines.length}</span></div>
      ${deadlines.map(d => dlRow(d)).join('')}
    </div>`;
}

function dlRow(d) {
  const today = todayStr();
  const isPending = d.status === 'pending';
  const isOverdue = isPending && d.due_date < today;
  const isToday   = isPending && d.due_date === today;

  const rowClass = isOverdue ? 'dl-row dl-overdue'
                 : isToday   ? 'dl-row dl-today'
                 : !isPending ? 'dl-row dl-done'
                 :              'dl-row';

  const priorityDot = d.priority === 'high'   ? '<span class="priority-dot priority-high" title="High priority"></span>'
                    : d.priority === 'medium'  ? '<span class="priority-dot priority-medium" title="Medium priority"></span>'
                    :                            '<span class="priority-dot priority-low" title="Low priority"></span>';

  const statusBadge = isPending ? '' : statusBadgeHtml(d.status);

  const dateLabel = isOverdue ? `<span class="text-danger fw-semibold">${daysLabel(d.due_date)}</span>`
                  : isToday   ? `<span class="text-warning fw-semibold">Due today</span>`
                  :              `<span class="text-muted">${formatDate(d.due_date)}</span>`;

  const quickBtns = isPending ? `
    <button class="btn btn-xs btn-success" onclick="quickStatus(${d.id},'completed')" title="Mark complete">
      <i class="fa-solid fa-check"></i>
    </button>
    <button class="btn btn-xs btn-secondary" onclick="quickStatus(${d.id},'waived')" title="Mark waived">
      <i class="fa-solid fa-ban"></i>
    </button>
    <button class="btn btn-xs btn-warning text-dark" onclick="quickStatus(${d.id},'expired')" title="Mark expired">
      <i class="fa-solid fa-hourglass-end"></i>
    </button>` : `
    <button class="btn btn-xs btn-outline-secondary" onclick="quickStatus(${d.id},'pending')" title="Reopen">
      <i class="fa-solid fa-rotate-left"></i>
    </button>`;

  return `
  <div class="${rowClass}" id="dl-${d.id}">
    <div class="dl-left">
      ${priorityDot}
      <span class="dl-cat-icon">${catIcon(d.category)}</span>
      <div class="dl-info">
        <div class="dl-title ${!isPending ? 'text-decoration-line-through text-muted' : ''}">${esc(d.title)}</div>
        ${d.description ? `<div class="dl-desc">${esc(d.description)}</div>` : ''}
        ${d.notes ? `<div class="dl-notes"><i class="fa-regular fa-note-sticky me-1"></i>${esc(d.notes)}</div>` : ''}
        ${d.completed_at ? `<div class="dl-completed-at">Completed ${formatDateTime(d.completed_at)}</div>` : ''}
      </div>
    </div>
    <div class="dl-right">
      <div class="dl-date-area">
        ${dateLabel}
        <div class="small text-muted">${d.due_time || '17:00'}</div>
        ${statusBadge}
      </div>
      <div class="dl-actions">
        ${quickBtns}
        <button class="btn btn-xs btn-outline-secondary" onclick="openDeadlineModal(${d.id})" title="Edit">
          <i class="fa-solid fa-pen"></i>
        </button>
        <button class="btn btn-xs btn-outline-danger" onclick="confirmDeleteDeadline(${d.id})" title="Delete">
          <i class="fa-solid fa-trash"></i>
        </button>
      </div>
    </div>
  </div>`;
}

// ─────────────────────────────────────────────── Transaction Modal ───
function openTransactionModal(tx) {
  const isEdit = !!tx;
  document.getElementById('txModalTitle').textContent = isEdit ? 'Edit Transaction' : 'New Transaction';
  document.getElementById('templateSection').classList.toggle('d-none', isEdit);

  document.getElementById('txId').value            = tx?.id           ?? '';
  document.getElementById('txAddress').value        = tx?.address      ?? '';
  document.getElementById('txCity').value           = tx?.city         ?? '';
  document.getElementById('txState').value          = tx?.state        ?? '';
  document.getElementById('txZip').value            = tx?.zip_code     ?? '';
  document.getElementById('txMls').value            = tx?.mls_number   ?? '';
  document.getElementById('txPrice').value          = tx?.purchase_price ?? '';
  document.getElementById('txType').value           = tx?.type         ?? 'buyer';
  document.getElementById('txStatus').value         = tx?.status       ?? 'active';
  document.getElementById('txContractDate').value   = tx?.contract_date ?? '';
  document.getElementById('txClosingDate').value    = tx?.closing_date  ?? '';
  document.getElementById('txClientName').value     = tx?.client_name  ?? '';
  document.getElementById('txClientPhone').value    = tx?.client_phone ?? '';
  document.getElementById('txClientEmail').value    = tx?.client_email ?? '';
  document.getElementById('txAgentName').value      = tx?.agent_name   ?? '';
  document.getElementById('txCoAgent').value        = tx?.co_agent     ?? '';
  document.getElementById('txLenderName').value     = tx?.lender_name  ?? '';
  document.getElementById('txLenderPhone').value    = tx?.lender_phone ?? '';
  document.getElementById('txTitleCompany').value   = tx?.title_company ?? '';
  document.getElementById('txTitleContact').value   = tx?.title_contact ?? '';
  document.getElementById('txNotes').value          = tx?.notes        ?? '';
  document.getElementById('txTemplate').value       = '';

  bootstrap.Modal.getOrCreateInstance(document.getElementById('transactionModal')).show();
}

function editCurrentTransaction() {
  openTransactionModal(S.currentTx);
}

async function saveTransaction() {
  const id = document.getElementById('txId').value;
  const data = {
    address:       document.getElementById('txAddress').value.trim(),
    city:          document.getElementById('txCity').value.trim(),
    state:         document.getElementById('txState').value.trim(),
    zip_code:      document.getElementById('txZip').value.trim(),
    mls_number:    document.getElementById('txMls').value.trim(),
    purchase_price:document.getElementById('txPrice').value || null,
    type:          document.getElementById('txType').value,
    status:        document.getElementById('txStatus').value,
    contract_date: document.getElementById('txContractDate').value || null,
    closing_date:  document.getElementById('txClosingDate').value  || null,
    client_name:   document.getElementById('txClientName').value.trim(),
    client_phone:  document.getElementById('txClientPhone').value.trim(),
    client_email:  document.getElementById('txClientEmail').value.trim(),
    agent_name:    document.getElementById('txAgentName').value.trim(),
    co_agent:      document.getElementById('txCoAgent').value.trim(),
    lender_name:   document.getElementById('txLenderName').value.trim(),
    lender_phone:  document.getElementById('txLenderPhone').value.trim(),
    title_company: document.getElementById('txTitleCompany').value.trim(),
    title_contact: document.getElementById('txTitleContact').value.trim(),
    notes:         document.getElementById('txNotes').value.trim(),
    template:      document.getElementById('txTemplate').value || null,
  };

  if (!data.address) { showToast('Address is required.', 'danger'); return; }

  try {
    let tx;
    if (id) {
      tx = await api('PUT', `/api/transactions/${id}`, data);
      if (S.currentTx && S.currentTx.id === parseInt(id)) {
        // Reload full transaction with deadlines
        S.currentTx = await api('GET', `/api/transactions/${id}`);
        renderTransactionDetail();
      }
      showToast('Transaction updated.', 'success');
    } else {
      tx = await api('POST', '/api/transactions', data);
      showToast('Transaction created.', 'success');
    }
    bootstrap.Modal.getOrCreateInstance(document.getElementById('transactionModal')).hide();
    showDashboard();
  } catch (e) {
    showToast('Error saving transaction: ' + e.message, 'danger');
  }
}

async function deleteCurrentTransaction() {
  const tx = S.currentTx;
  showConfirm(
    `Delete "${tx.address}"? All deadlines will be permanently removed.`,
    async () => {
      try {
        await api('DELETE', `/api/transactions/${tx.id}`);
        showToast('Transaction deleted.', 'success');
        showDashboard();
      } catch (e) { showToast('Error: ' + e.message, 'danger'); }
    }
  );
}

// ─────────────────────────────────────────────── Deadline Modal ───
function openDeadlineModal(id) {
  const isEdit = typeof id === 'number';
  document.getElementById('dlModalTitle').textContent = isEdit ? 'Edit Deadline' : 'Add Deadline';
  document.getElementById('dlTransactionId').value = S.currentTx.id;

  let d = null;
  if (isEdit) d = S.currentTx.deadlines.find(x => x.id === id);

  document.getElementById('dlId').value          = d?.id          ?? '';
  document.getElementById('dlTitle').value       = d?.title       ?? '';
  document.getElementById('dlDueDate').value     = d?.due_date    ?? '';
  document.getElementById('dlDueTime').value     = d?.due_time    ?? '17:00';
  document.getElementById('dlCategory').value    = d?.category    ?? 'custom';
  document.getElementById('dlPriority').value    = d?.priority    ?? 'medium';
  document.getElementById('dlStatus').value      = d?.status      ?? 'pending';
  document.getElementById('dlDescription').value = d?.description ?? '';
  document.getElementById('dlNotes').value       = d?.notes       ?? '';

  bootstrap.Modal.getOrCreateInstance(document.getElementById('deadlineModal')).show();
}

async function saveDeadline() {
  const id  = document.getElementById('dlId').value;
  const tid = parseInt(document.getElementById('dlTransactionId').value);
  const data = {
    title:       document.getElementById('dlTitle').value.trim(),
    due_date:    document.getElementById('dlDueDate').value,
    due_time:    document.getElementById('dlDueTime').value || '17:00',
    category:    document.getElementById('dlCategory').value,
    priority:    document.getElementById('dlPriority').value,
    status:      document.getElementById('dlStatus').value,
    description: document.getElementById('dlDescription').value.trim(),
    notes:       document.getElementById('dlNotes').value.trim(),
  };

  if (!data.title)    { showToast('Title is required.', 'danger'); return; }
  if (!data.due_date) { showToast('Due date is required.', 'danger'); return; }

  try {
    if (id) {
      await api('PUT', `/api/deadlines/${id}`, data);
      showToast('Deadline updated.', 'success');
    } else {
      await api('POST', `/api/transactions/${tid}/deadlines`, data);
      showToast('Deadline added.', 'success');
    }
    bootstrap.Modal.getOrCreateInstance(document.getElementById('deadlineModal')).hide();
    await refreshCurrentTx();
  } catch (e) { showToast('Error: ' + e.message, 'danger'); }
}

async function quickStatus(did, status) {
  try {
    await api('POST', `/api/deadlines/${did}/status`, { status });
    await refreshCurrentTx();
    showToast(`Marked as ${status}.`, 'success');
  } catch (e) { showToast('Error: ' + e.message, 'danger'); }
}

function confirmDeleteDeadline(did) {
  const d = S.currentTx.deadlines.find(x => x.id === did);
  showConfirm(`Delete "${d?.title || 'this deadline'}"?`, async () => {
    try {
      await api('DELETE', `/api/deadlines/${did}`);
      showToast('Deadline deleted.', 'success');
      await refreshCurrentTx();
    } catch (e) { showToast('Error: ' + e.message, 'danger'); }
  });
}

async function refreshCurrentTx() {
  if (!S.currentTx) return;
  S.currentTx = await api('GET', `/api/transactions/${S.currentTx.id}`);
  renderDeadlines();
}

// ─────────────────────────────────────────────── Template Modal ───
async function loadTemplates() {
  try {
    S.templates = await api('GET', '/api/templates');
    const sel = document.getElementById('txTemplate');
    const tplSel = document.getElementById('tplSelect');
    Object.entries(S.templates).forEach(([key, tpl]) => {
      const opt1 = new Option(`${tpl.name} (${tpl.count} deadlines)`, key);
      sel.appendChild(opt1);
      const opt2 = new Option(`${tpl.name} (${tpl.count} deadlines)`, key);
      tplSel.appendChild(opt2);
    });
    updateTemplateInfo();
  } catch (e) { console.error(e); }
}

function openTemplateModal() {
  document.getElementById('tplContractDate').value = S.currentTx?.contract_date || '';
  updateTemplateInfo();
  bootstrap.Modal.getOrCreateInstance(document.getElementById('templateModal')).show();
}

function updateTemplateInfo() {
  const key = document.getElementById('tplSelect').value;
  const el  = document.getElementById('tplInfo');
  if (key && S.templates[key]) {
    el.textContent = `${S.templates[key].count} deadlines will be added.`;
  } else {
    el.textContent = '';
  }
}

async function applyTemplate() {
  const key          = document.getElementById('tplSelect').value;
  const contractDate = document.getElementById('tplContractDate').value;
  if (!key)          { showToast('Please select a template.', 'danger'); return; }
  if (!contractDate) { showToast('Please enter a contract/base date.', 'danger'); return; }

  try {
    const res = await api('POST', `/api/transactions/${S.currentTx.id}/apply-template`, {
      template: key, contract_date: contractDate
    });
    bootstrap.Modal.getOrCreateInstance(document.getElementById('templateModal')).hide();
    showToast(`Added ${res.added} deadlines from template.`, 'success');
    await refreshCurrentTx();
  } catch (e) { showToast('Error: ' + e.message, 'danger'); }
}

// ─────────────────────────────────────────────── Confirm helper ───
function showConfirm(message, onConfirm) {
  document.getElementById('confirmMessage').textContent = message;
  const btn = document.getElementById('confirmBtn');
  const newBtn = btn.cloneNode(true);
  btn.parentNode.replaceChild(newBtn, btn);
  newBtn.addEventListener('click', () => {
    bootstrap.Modal.getOrCreateInstance(document.getElementById('confirmModal')).hide();
    onConfirm();
  });
  bootstrap.Modal.getOrCreateInstance(document.getElementById('confirmModal')).show();
}

// ─────────────────────────────────────────────── Toast ───
function showToast(msg, type = 'success') {
  const el = document.getElementById('appToast');
  el.className = `toast align-items-center text-bg-${type} border-0`;
  document.getElementById('toastMsg').textContent = msg;
  bootstrap.Toast.getOrCreateInstance(el, { delay: 3000 }).show();
}

// ─────────────────────────────────────────────── Utilities ───
function esc(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

function daysUntil(dateStr) {
  const d = new Date(dateStr + 'T00:00:00');
  const t = new Date(); t.setHours(0, 0, 0, 0);
  return Math.round((d - t) / 86400000);
}

function daysLabel(dateStr) {
  const n = daysUntil(dateStr);
  if (n === 0)  return 'Due today';
  if (n === 1)  return 'Due tomorrow';
  if (n === -1) return '1 day overdue';
  if (n > 0)    return `${n} days left`;
  return `${Math.abs(n)} days overdue`;
}

function formatDate(dateStr) {
  if (!dateStr) return '';
  const [y, m, d] = dateStr.split('-');
  return `${m}/${d}/${y}`;
}

function formatDateTime(isoStr) {
  if (!isoStr) return '';
  const d = new Date(isoStr);
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function urgencyClass(due_date, status) {
  if (status !== 'pending') return 'text-muted';
  const days = daysUntil(due_date);
  if (days < 0)  return 'text-danger fw-semibold';
  if (days === 0) return 'text-warning fw-semibold';
  if (days <= 3)  return 'text-warning';
  return 'text-muted';
}

function txStatusClass(status) {
  return {
    active:         'bg-primary',
    under_contract: 'bg-success',
    closed:         'bg-secondary',
    canceled:       'bg-danger',
    fallen_through: 'bg-warning text-dark',
  }[status] || 'bg-secondary';
}

function txStatusLabel(status) {
  return {
    active:         'Active',
    under_contract: 'Under Contract',
    closed:         'Closed',
    canceled:       'Canceled',
    fallen_through: 'Fallen Through',
  }[status] || status;
}

function txTypeLabel(type) {
  return {
    buyer:    'Buyer Representation',
    seller:   'Seller / Listing',
    both:     'Both Sides',
    lease:    'Lease',
    refinance:'Refinance',
  }[type] || type;
}

function txTypeIcon(type) {
  return {
    buyer:    '<i class="fa-solid fa-person-walking-arrow-right text-primary"></i>',
    seller:   '<i class="fa-solid fa-sign-hanging text-success"></i>',
    both:     '<i class="fa-solid fa-arrows-left-right text-info"></i>',
    lease:    '<i class="fa-solid fa-key text-warning"></i>',
    refinance:'<i class="fa-solid fa-rotate text-secondary"></i>',
  }[type] || '<i class="fa-solid fa-house"></i>';
}

function statusBadgeHtml(status) {
  const map = {
    completed: 'bg-success',
    expired:   'bg-secondary',
    waived:    'bg-info text-dark',
    canceled:  'bg-danger',
    pending:   'bg-primary',
  };
  return `<span class="badge ${map[status] || 'bg-secondary'}">${status}</span>`;
}

function catIcon(cat) {
  return {
    earnest_money: '<i class="fa-solid fa-dollar-sign cat-icon cat-money" title="Earnest Money"></i>',
    inspection:    '<i class="fa-solid fa-magnifying-glass cat-icon cat-inspect" title="Inspection"></i>',
    financing:     '<i class="fa-solid fa-university cat-icon cat-finance" title="Financing"></i>',
    appraisal:     '<i class="fa-solid fa-chart-bar cat-icon cat-appraisal" title="Appraisal"></i>',
    title:         '<i class="fa-solid fa-file-contract cat-icon cat-title" title="Title"></i>',
    hoa:           '<i class="fa-solid fa-building-user cat-icon cat-hoa" title="HOA"></i>',
    survey:        '<i class="fa-solid fa-ruler-combined cat-icon cat-survey" title="Survey"></i>',
    insurance:     '<i class="fa-solid fa-shield-halved cat-icon cat-insurance" title="Insurance"></i>',
    walkthrough:   '<i class="fa-solid fa-person-walking cat-icon cat-walk" title="Walkthrough"></i>',
    closing:       '<i class="fa-solid fa-handshake cat-icon cat-closing" title="Closing"></i>',
    disclosure:    '<i class="fa-solid fa-clipboard-list cat-icon cat-disclosure" title="Disclosure"></i>',
    custom:        '<i class="fa-solid fa-circle-dot cat-icon cat-custom" title="Custom"></i>',
  }[cat] || '<i class="fa-solid fa-circle-dot cat-icon cat-custom"></i>';
}
