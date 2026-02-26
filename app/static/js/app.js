/* ─── Work Hours Tracker - Frontend Logic ─────────────────────────────── */

const API = '/api';

// ─── State ───────────────────────────────────────────────────────────────

let state = {
    entries: [],
    editingId: null,
    dailyTarget: 7.6,
    calYear: new Date().getFullYear(),
    calMonth: new Date().getMonth(), // 0-indexed
    weeklyYear: new Date().getFullYear(),
    weeklyMonth: new Date().getMonth(),
};

// ─── Init ────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
    initTheme();
    initTabs();
    initForm();
    initAdjustmentForm();
    initExport();
    initTargetEdit();
    await loadSettings();
    setDefaults();
    loadTotalSummary();
    loadEntries();
    loadAdjustments();
});

// ─── Theme ───────────────────────────────────────────────────────────────

function initTheme() {
    const saved = localStorage.getItem('theme');
    if (saved) {
        document.documentElement.setAttribute('data-theme', saved);
    } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
        document.documentElement.setAttribute('data-theme', 'dark');
    }

    document.getElementById('themeToggle').addEventListener('click', () => {
        const current = document.documentElement.getAttribute('data-theme');
        const next = current === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        localStorage.setItem('theme', next);
    });
}

// ─── Settings ────────────────────────────────────────────────────────────

async function loadSettings() {
    try {
        const res = await fetch(`${API}/settings`);
        const data = await res.json();
        state.dailyTarget = data.daily_target;
    } catch { /* use default */ }
}

function initTargetEdit() {
    const stat = document.getElementById('targetStat');
    stat.addEventListener('click', () => {
        // Already editing?
        if (stat.querySelector('.stat-edit-input')) return;

        const valueEl = document.getElementById('dailyTarget');
        const currentVal = state.dailyTarget;
        const originalHTML = stat.innerHTML;

        stat.innerHTML = `
            <input type="number" class="stat-edit-input" value="${currentVal}" step="0.1" min="0.1" max="24" autofocus>
            <div class="stat-edit-actions">
                <button class="stat-edit-save" title="Save">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="14" height="14">
                        <polyline points="20 6 9 17 4 12"/>
                    </svg>
                </button>
                <button class="stat-edit-cancel" title="Cancel">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="14" height="14">
                        <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                    </svg>
                </button>
            </div>
        `;

        const input = stat.querySelector('.stat-edit-input');
        input.focus();
        input.select();

        const cancel = () => {
            stat.innerHTML = originalHTML;
            document.getElementById('dailyTarget').textContent = state.dailyTarget.toFixed(2);
        };

        const save = () => {
            const val = parseFloat(input.value);
            if (isNaN(val) || val <= 0 || val > 24) {
                showToast('Target must be between 0 and 24 hours', 'error');
                return;
            }
            saveTarget(val);
        };

        stat.querySelector('.stat-edit-save').addEventListener('click', (e) => {
            e.stopPropagation();
            save();
        });
        stat.querySelector('.stat-edit-cancel').addEventListener('click', (e) => {
            e.stopPropagation();
            cancel();
        });
        input.addEventListener('click', (e) => e.stopPropagation());
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') save();
            if (e.key === 'Escape') cancel();
        });
    });
}

async function saveTarget(value) {
    try {
        const res = await fetch(`${API}/settings`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ daily_target: value }),
        });

        if (!res.ok) {
            const data = await res.json();
            showToast(data.error || 'Failed to save target', 'error');
            return;
        }

        state.dailyTarget = value;
        showToast(`Daily target set to ${value}h`, 'success');

        // Restore the stat display
        const stat = document.getElementById('targetStat');
        stat.innerHTML = `
            <span class="stat-value" id="dailyTarget">${value.toFixed(2)}</span>
            <span class="stat-label">daily target
                <svg class="stat-edit-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="10" height="10">
                    <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                    <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                </svg>
            </span>
        `;

        // Refresh dependent views
        updatePreview();
        loadTotalSummary();
    } catch {
        showToast('Network error. Please try again.', 'error');
    }
}

// ─── Tabs ────────────────────────────────────────────────────────────────

function initTabs() {
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById(`tab-${tab.dataset.tab}`).classList.add('active');

            // Load data for tab
            switch (tab.dataset.tab) {
                case 'entry': loadEntries(); break;
                case 'weekly': loadWeeklySummary(); break;
                case 'monthly': loadMonthlySummary(); break;
                case 'calendar': loadCalendar(); break;
            }
        });
    });
}

// ─── Form ────────────────────────────────────────────────────────────────

function initForm() {
    const form = document.getElementById('entryForm');
    form.addEventListener('submit', handleSubmit);

    // Live preview
    ['startTime', 'endTime'].forEach(id => {
        document.getElementById(id).addEventListener('input', updatePreview);
    });

    // Add break button
    document.getElementById('addBreakBtn').addEventListener('click', addBreakRow);

    // Cancel edit
    document.getElementById('cancelEditBtn').addEventListener('click', cancelEdit);

    // Delete modal
    document.getElementById('cancelDelete').addEventListener('click', () => {
        document.getElementById('deleteModal').style.display = 'none';
    });
}

function setDefaults() {
    document.getElementById('entryDate').value = todayStr();
    document.getElementById('startTime').value = '08:00';
    document.getElementById('endTime').value = '16:00';
    updatePreview();
}

function addBreakRow(defaultStart = '', defaultEnd = '') {
    const container = document.getElementById('breaksContainer');
    const row = document.createElement('div');
    row.className = 'break-row';
    const startVal = typeof defaultStart === 'string' ? defaultStart : '';
    const endVal = typeof defaultEnd === 'string' ? defaultEnd : '';
    row.innerHTML = `
        <input type="time" class="break-start" value="${startVal}" placeholder="Start">
        <span class="break-dash">&ndash;</span>
        <input type="time" class="break-end" value="${endVal}" placeholder="End">
        <button type="button" class="break-remove" title="Remove break">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
        </button>
    `;

    row.querySelector('.break-remove').addEventListener('click', () => {
        row.remove();
        updatePreview();
    });

    row.querySelectorAll('input').forEach(inp => {
        inp.addEventListener('input', updatePreview);
    });

    container.appendChild(row);
    updatePreview();
}

function getBreaks() {
    const breaks = [];
    document.querySelectorAll('.break-row').forEach(row => {
        const start = row.querySelector('.break-start').value;
        const end = row.querySelector('.break-end').value;
        if (start && end) {
            breaks.push({ start, end });
        }
    });
    return breaks;
}

function updatePreview() {
    const start = document.getElementById('startTime').value;
    const end = document.getElementById('endTime').value;

    if (!start || !end) {
        setPreviewValues('--:--', '--:--', '--:--', '--:--', '');
        return;
    }

    const startMin = timeToMinutes(start);
    let endMin = timeToMinutes(end);
    if (endMin <= startMin) endMin += 24 * 60;

    const grossMin = endMin - startMin;
    const breaks = getBreaks();
    let breakMin = 0;
    breaks.forEach(b => {
        const bs = timeToMinutes(b.start);
        const be = timeToMinutes(b.end);
        if (be > bs) breakMin += be - bs;
    });

    const netMin = grossMin - breakMin;
    const netHours = netMin / 60;
    const balance = netHours - state.dailyTarget;

    setPreviewValues(
        formatMinutes(grossMin),
        formatMinutes(breakMin),
        formatMinutes(Math.max(netMin, 0)),
        formatBalance(balance),
        balance >= 0 ? 'positive' : 'negative'
    );
}

function setPreviewValues(gross, breaks, net, balance, balanceClass) {
    document.getElementById('previewGross').textContent = gross;
    document.getElementById('previewBreaks').textContent = breaks;
    document.getElementById('previewNet').textContent = net;
    const balEl = document.getElementById('previewBalance');
    balEl.textContent = balance;
    balEl.className = `preview-value ${balanceClass}`;
}

async function handleSubmit(e) {
    e.preventDefault();

    const data = {
        date: document.getElementById('entryDate').value,
        start_time: document.getElementById('startTime').value,
        end_time: document.getElementById('endTime').value,
        breaks: getBreaks(),
        note: document.getElementById('entryNote').value,
    };

    if (!data.date || !data.start_time || !data.end_time) {
        showToast('Please fill in date, start and end time', 'error');
        return;
    }

    try {
        let res;
        if (state.editingId) {
            res = await fetch(`${API}/entries/${state.editingId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });
        } else {
            res = await fetch(`${API}/entries`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });
        }

        const result = await res.json();
        if (!res.ok) {
            showToast(result.error || 'Failed to save entry', 'error');
            return;
        }

        showToast(state.editingId ? 'Entry updated' : 'Entry saved', 'success');
        cancelEdit();
        loadEntries();
        loadTotalSummary();
    } catch (err) {
        showToast('Network error. Please try again.', 'error');
    }
}

function cancelEdit() {
    state.editingId = null;
    document.getElementById('entryId').value = '';
    document.getElementById('formTitle').textContent = 'New Entry';
    document.getElementById('submitBtn').textContent = 'Save Entry';
    document.getElementById('cancelEditBtn').style.display = 'none';
    document.getElementById('entryForm').reset();
    document.getElementById('breaksContainer').innerHTML = '';
    setDefaults();
}

function editEntry(entry) {
    state.editingId = entry.id;
    document.getElementById('entryId').value = entry.id;
    document.getElementById('entryDate').value = entry.date;
    document.getElementById('startTime').value = entry.start_time;
    document.getElementById('endTime').value = entry.end_time;
    document.getElementById('entryNote').value = entry.note || '';
    document.getElementById('formTitle').textContent = 'Edit Entry';
    document.getElementById('submitBtn').textContent = 'Update Entry';
    document.getElementById('cancelEditBtn').style.display = 'inline-flex';

    // Populate breaks
    document.getElementById('breaksContainer').innerHTML = '';
    (entry.breaks || []).forEach(b => addBreakRow(b.start, b.end));

    updatePreview();

    // Switch to entry tab
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.querySelector('[data-tab="entry"]').classList.add('active');
    document.getElementById('tab-entry').classList.add('active');

    // Scroll to form
    document.querySelector('.entry-form-card').scrollIntoView({ behavior: 'smooth' });
}

function deleteEntry(id) {
    const modal = document.getElementById('deleteModal');
    modal.style.display = 'flex';

    const confirmBtn = document.getElementById('confirmDelete');
    const handler = async () => {
        modal.style.display = 'none';
        confirmBtn.removeEventListener('click', handler);
        try {
            const res = await fetch(`${API}/entries/${id}`, { method: 'DELETE' });
            if (res.ok) {
                showToast('Entry deleted', 'success');
                loadEntries();
                loadTotalSummary();
            } else {
                showToast('Failed to delete entry', 'error');
            }
        } catch {
            showToast('Network error', 'error');
        }
    };
    confirmBtn.addEventListener('click', handler);
}

// ─── Load Data ───────────────────────────────────────────────────────────

async function loadEntries() {
    try {
        const res = await fetch(`${API}/entries`);
        const entries = await res.json();
        state.entries = entries;
        renderEntries(entries);
    } catch {
        document.getElementById('entriesList').innerHTML =
            '<div class="empty-state"><p>Failed to load entries</p></div>';
    }
}

async function loadTotalSummary() {
    try {
        const res = await fetch(`${API}/summary/total`);
        const data = await res.json();

        const otEl = document.getElementById('totalOvertime');
        otEl.textContent = formatHoursBalance(data.combined_balance);
        otEl.className = 'overtime-value ' +
            (data.combined_balance > 0.01 ? 'positive' : data.combined_balance < -0.01 ? 'negative' : 'neutral');

        document.getElementById('totalDays').textContent = data.total_days;
        document.getElementById('totalHours').textContent = data.total_hours.toFixed(2);
        document.getElementById('dailyTarget').textContent = data.daily_target.toFixed(2);
        document.getElementById('manualAdj').textContent = formatHoursBalance(data.manual_adjustment);
    } catch { /* ignore */ }
}

async function loadWeeklySummary() {
    const el = document.getElementById('weeklySummary');
    el.innerHTML = '<div class="loading">Loading...</div>';

    updateMonthLabel('weeklyMonth', state.weeklyYear, state.weeklyMonth);
    initMonthNav('weeklyPrev', 'weeklyNext', 'weekly');

    try {
        const y = state.weeklyYear;
        const m = state.weeklyMonth + 1;
        const res = await fetch(`${API}/summary/weekly?year=${y}&month=${m}`);
        const weeks = await res.json();

        if (weeks.length === 0) {
            el.innerHTML = '<div class="empty-state"><p>No entries for this month</p></div>';
            return;
        }

        el.innerHTML = weeks.map(w => {
            const pct = Math.min((w.total_hours / w.target) * 100, 120);
            const cls = w.overtime > 0.01 ? 'overtime' : w.overtime < -0.01 ? 'undertime' : 'on-target';
            const otCls = w.overtime > 0.01 ? 'positive' : w.overtime < -0.01 ? 'negative' : 'neutral';
            return `
                <div class="summary-item">
                    <div class="summary-info">
                        <h3>${w.week}</h3>
                        <div class="summary-meta">
                            <span>${w.monday} &rarr; ${w.sunday}</span>
                            <span>${w.days_worked} day${w.days_worked !== 1 ? 's' : ''}</span>
                        </div>
                        <div class="progress-bar-container">
                            <div class="progress-bar ${cls}" style="width: ${pct}%"></div>
                        </div>
                    </div>
                    <div class="summary-balance">
                        <div class="summary-hours">${w.total_hours.toFixed(2)}h / ${w.target.toFixed(2)}h</div>
                        <div class="summary-overtime ${otCls}">${formatHoursBalance(w.overtime)}</div>
                    </div>
                </div>`;
        }).join('');
    } catch {
        el.innerHTML = '<div class="empty-state"><p>Failed to load weekly summary</p></div>';
    }
}

async function loadMonthlySummary() {
    const el = document.getElementById('monthlySummary');
    el.innerHTML = '<div class="loading">Loading...</div>';

    try {
        const res = await fetch(`${API}/summary/monthly`);
        const months = await res.json();

        if (months.length === 0) {
            el.innerHTML = '<div class="empty-state"><p>No entries yet</p></div>';
            return;
        }

        el.innerHTML = months.map(m => {
            const pct = Math.min((m.total_hours / m.target) * 100, 120);
            const cls = m.overtime > 0.01 ? 'overtime' : m.overtime < -0.01 ? 'undertime' : 'on-target';
            const otCls = m.overtime > 0.01 ? 'positive' : m.overtime < -0.01 ? 'negative' : 'neutral';
            const [y, mo] = m.month.split('-');
            const monthName = new Date(y, mo - 1).toLocaleString('default', { month: 'long', year: 'numeric' });
            return `
                <div class="summary-item">
                    <div class="summary-info">
                        <h3>${monthName}</h3>
                        <div class="summary-meta">
                            <span>${m.days_worked} day${m.days_worked !== 1 ? 's' : ''} logged</span>
                        </div>
                        <div class="progress-bar-container">
                            <div class="progress-bar ${cls}" style="width: ${pct}%"></div>
                        </div>
                    </div>
                    <div class="summary-balance">
                        <div class="summary-hours">${m.total_hours.toFixed(2)}h / ${m.target.toFixed(2)}h</div>
                        <div class="summary-overtime ${otCls}">${formatHoursBalance(m.overtime)}</div>
                    </div>
                </div>`;
        }).join('');
    } catch {
        el.innerHTML = '<div class="empty-state"><p>Failed to load monthly summary</p></div>';
    }
}

async function loadCalendar() {
    const grid = document.getElementById('calendarGrid');
    grid.innerHTML = '<div class="loading" style="grid-column: 1/-1">Loading...</div>';

    updateMonthLabel('calMonth', state.calYear, state.calMonth);
    initMonthNav('calPrev', 'calNext', 'cal');

    try {
        const y = state.calYear;
        const m = state.calMonth + 1;
        const res = await fetch(`${API}/entries?year=${y}&month=${m}`);
        const entries = await res.json();

        // Map entries by date
        const byDate = {};
        entries.forEach(e => { byDate[e.date] = e; });

        const today = todayStr();
        const firstDay = new Date(y, state.calMonth, 1);
        const daysInMonth = new Date(y, state.calMonth + 1, 0).getDate();
        let startDay = firstDay.getDay(); // 0=Sun
        // Convert to Mon=0 ... Sun=6
        startDay = startDay === 0 ? 6 : startDay - 1;

        let html = '';
        // Headers
        ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].forEach(d => {
            html += `<div class="cal-header">${d}</div>`;
        });

        // Empty cells
        for (let i = 0; i < startDay; i++) {
            html += '<div class="cal-day empty"></div>';
        }

        // Days
        for (let d = 1; d <= daysInMonth; d++) {
            const dateStr = `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
            const entry = byDate[dateStr];
            const isToday = dateStr === today;
            let cls = 'no-entry';
            let hoursText = '';

            if (entry) {
                if (entry.overtime > 0.01) cls = 'overtime';
                else if (entry.overtime < -0.01) cls = 'undertime';
                else cls = 'on-target';
                hoursText = `<span class="cal-hours">${entry.total_hours.toFixed(1)}h</span>`;
            }

            html += `<div class="cal-day ${cls}${isToday ? ' today' : ''}" title="${entry ? entry.total_hours.toFixed(2) + 'h' : 'No entry'}">${d}${hoursText}</div>`;
        }

        grid.innerHTML = html;
    } catch {
        grid.innerHTML = '<div class="empty-state" style="grid-column:1/-1"><p>Failed to load calendar</p></div>';
    }
}

// ─── Render ──────────────────────────────────────────────────────────────

function renderEntries(entries) {
    const el = document.getElementById('entriesList');

    if (entries.length === 0) {
        el.innerHTML = `
            <div class="empty-state">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="48" height="48">
                    <rect x="3" y="4" width="18" height="18" rx="2"/>
                    <line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/>
                    <line x1="3" y1="10" x2="21" y2="10"/>
                </svg>
                <p>No entries yet. Add your first one above!</p>
            </div>`;
        return;
    }

    el.innerHTML = entries.map(entry => {
        const otCls = entry.overtime > 0.01 ? 'positive' : entry.overtime < -0.01 ? 'negative' : 'neutral';
        const dateObj = new Date(entry.date + 'T00:00:00');
        const dayName = dateObj.toLocaleDateString('default', { weekday: 'short' });
        const dateDisplay = dateObj.toLocaleDateString('default', { month: 'short', day: 'numeric', year: 'numeric' });
        const breakCount = entry.breaks ? entry.breaks.length : 0;
        const breakInfo = breakCount > 0 ? ` | ${breakCount} break${breakCount > 1 ? 's' : ''}` : '';

        return `
            <div class="entry-item">
                <div class="entry-info">
                    <div class="entry-date">${dayName}, ${dateDisplay}</div>
                    <div class="entry-times">${entry.start_time} &ndash; ${entry.end_time}${breakInfo}${entry.note ? ' | ' + escapeHtml(entry.note) : ''}</div>
                </div>
                <div class="entry-hours">
                    <span class="entry-total">${entry.total_hours.toFixed(2)}h</span>
                    <span class="entry-overtime ${otCls}">${formatHoursBalance(entry.overtime)}</span>
                </div>
                <div class="entry-actions">
                    <button class="edit-btn" onclick="editEntry(${escapeHtml(JSON.stringify(entry).replace(/"/g, '&quot;'))})" title="Edit">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                            <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                            <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                        </svg>
                    </button>
                    <button class="delete-btn" onclick="deleteEntry(${entry.id})" title="Delete">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                            <polyline points="3 6 5 6 21 6"/>
                            <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                        </svg>
                    </button>
                </div>
            </div>`;
    }).join('');
}

// ─── Month Navigation ────────────────────────────────────────────────────

function initMonthNav(prevId, nextId, type) {
    const prevBtn = document.getElementById(prevId);
    const nextBtn = document.getElementById(nextId);

    // Remove old listeners by cloning
    const newPrev = prevBtn.cloneNode(true);
    const newNext = nextBtn.cloneNode(true);
    prevBtn.replaceWith(newPrev);
    nextBtn.replaceWith(newNext);

    newPrev.addEventListener('click', () => {
        if (type === 'cal') {
            state.calMonth--;
            if (state.calMonth < 0) { state.calMonth = 11; state.calYear--; }
            loadCalendar();
        } else {
            state.weeklyMonth--;
            if (state.weeklyMonth < 0) { state.weeklyMonth = 11; state.weeklyYear--; }
            loadWeeklySummary();
        }
    });

    newNext.addEventListener('click', () => {
        if (type === 'cal') {
            state.calMonth++;
            if (state.calMonth > 11) { state.calMonth = 0; state.calYear++; }
            loadCalendar();
        } else {
            state.weeklyMonth++;
            if (state.weeklyMonth > 11) { state.weeklyMonth = 0; state.weeklyYear++; }
            loadWeeklySummary();
        }
    });
}

function updateMonthLabel(labelId, year, month) {
    const label = document.getElementById(labelId);
    const date = new Date(year, month);
    label.textContent = date.toLocaleDateString('default', { month: 'long', year: 'numeric' });
}

// ─── Export ──────────────────────────────────────────────────────────────

function initExport() {
    document.getElementById('exportBtn').addEventListener('click', () => {
        window.location.href = `${API}/export/csv`;
        showToast('Downloading CSV...', 'info');
    });
}

// ─── Adjustments ─────────────────────────────────────────────────────────

function initAdjustmentForm() {
    const form = document.getElementById('adjustmentForm');
    form.addEventListener('submit', (e) => {
        e.preventDefault();
        createAdjustment();
    });
}

async function loadAdjustments() {
    const el = document.getElementById('adjustmentsList');
    try {
        const res = await fetch(`${API}/adjustments`);
        const adjustments = await res.json();

        if (adjustments.length === 0) {
            el.innerHTML = '<div class="empty-state"><p>No adjustments yet.</p></div>';
            return;
        }

        el.innerHTML = adjustments.map(adj => {
            const cls = adj.hours >= 0 ? 'positive' : 'negative';
            const sign = adj.hours >= 0 ? '+' : '';
            return `
                <div class="adjustment-item">
                    <span class="adjustment-hours ${cls}">${sign}${adj.hours.toFixed(2)}h</span>
                    <span class="adjustment-reason">${escapeHtml(adj.reason)}</span>
                    <button class="delete-btn" onclick="deleteAdjustment(${adj.id})" title="Delete adjustment">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                            <polyline points="3 6 5 6 21 6"/>
                            <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                        </svg>
                    </button>
                </div>`;
        }).join('');
    } catch {
        el.innerHTML = '<div class="empty-state"><p>Failed to load adjustments.</p></div>';
    }
}

async function createAdjustment() {
    const hoursInput = document.getElementById('adjHours');
    const reasonInput = document.getElementById('adjReason');

    const hours = parseFloat(hoursInput.value);
    const reason = reasonInput.value.trim();

    if (isNaN(hours)) {
        showToast('Please enter a valid number for hours', 'error');
        return;
    }
    if (!reason) {
        showToast('Please enter a reason', 'error');
        return;
    }

    try {
        const res = await fetch(`${API}/adjustments`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ hours, reason }),
        });

        const result = await res.json();
        if (!res.ok) {
            showToast(result.error || 'Failed to create adjustment', 'error');
            return;
        }

        showToast('Adjustment added', 'success');
        hoursInput.value = '';
        reasonInput.value = '';
        loadAdjustments();
        loadTotalSummary();
    } catch {
        showToast('Network error. Please try again.', 'error');
    }
}

async function deleteAdjustment(id) {
    if (!confirm('Delete this adjustment?')) return;

    try {
        const res = await fetch(`${API}/adjustments/${id}`, { method: 'DELETE' });
        if (res.ok) {
            showToast('Adjustment deleted', 'success');
            loadAdjustments();
            loadTotalSummary();
        } else {
            showToast('Failed to delete adjustment', 'error');
        }
    } catch {
        showToast('Network error', 'error');
    }
}

// ─── Helpers ─────────────────────────────────────────────────────────────

function todayStr() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function timeToMinutes(timeStr) {
    const [h, m] = timeStr.split(':').map(Number);
    return h * 60 + m;
}

function formatMinutes(min) {
    const h = Math.floor(Math.abs(min) / 60);
    const m = Math.abs(min) % 60;
    return `${h}:${String(Math.round(m)).padStart(2, '0')}`;
}

function formatBalance(hours) {
    const sign = hours >= 0 ? '+' : '-';
    const abs = Math.abs(hours);
    const h = Math.floor(abs);
    const m = Math.round((abs - h) * 60);
    return `${sign}${h}:${String(m).padStart(2, '0')}`;
}

function formatHoursBalance(hours) {
    const sign = hours >= 0 ? '+' : '';
    return `${sign}${hours.toFixed(2)}h`;
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ─── Toast ───────────────────────────────────────────────────────────────

function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}
