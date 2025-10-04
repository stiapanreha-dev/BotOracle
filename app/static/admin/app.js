const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

const API_URL = window.location.origin;
let ADMIN_TOKEN = null;
let CURRENT_USER_TG_ID = null;

let currentUserFilter = '';
let currentSubFilter = '';

// Verify admin access on load
async function verifyAccess() {
    try {
        // Check if opened in Telegram
        if (!tg.initData) {
            showError('❌ Open this page in Telegram Mini App');
            return false;
        }

        const response = await fetch(`${API_URL}/admin/auth/verify`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                initData: tg.initData
            })
        });

        if (!response.ok) {
            if (response.status === 403) {
                showError('🚫 Access denied. Admin only.');
            } else {
                showError('❌ Authentication failed');
            }
            return false;
        }

        const data = await response.json();
        ADMIN_TOKEN = data.token;

        // Store current user Telegram ID
        if (data.user && data.user.id) {
            CURRENT_USER_TG_ID = data.user.id;
        }

        // Show username in header
        const header = document.querySelector('.header h1');
        if (data.user && data.user.first_name) {
            header.textContent = `📊 Admin Panel - ${data.user.first_name}`;
        }

        return true;
    } catch (error) {
        console.error('Error verifying access:', error);
        showError('❌ Connection error');
        return false;
    }
}

function showError(message) {
    document.body.innerHTML = `
        <div style="display: flex; align-items: center; justify-content: center; height: 100vh; padding: 20px; text-align: center;">
            <div>
                <div style="font-size: 48px; margin-bottom: 20px;">${message.split(' ')[0]}</div>
                <div style="font-size: 18px; opacity: 0.7;">${message.substring(message.indexOf(' ') + 1)}</div>
            </div>
        </div>
    `;
}

// Load dashboard data
async function loadDashboard() {
    try {
        const response = await fetch(`${API_URL}/admin/dashboard`, {
            headers: {
                'Authorization': `Bearer ${ADMIN_TOKEN}`
            }
        });
        const data = await response.json();

        document.getElementById('totalUsers').textContent = data.total_users || 0;
        document.getElementById('activeToday').textContent = data.active_today || 0;
        document.getElementById('activeWeek').textContent = data.active_week || 0;
        document.getElementById('newToday').textContent = data.new_today || 0;
        document.getElementById('activeSubs').textContent = data.active_subscriptions || 0;
        document.getElementById('todayRevenue').textContent = `${(data.today_revenue || 0).toFixed(0)}₽`;
        document.getElementById('monthRevenue').textContent = `${(data.month_revenue || 0).toFixed(0)}₽`;
        document.getElementById('paymentsToday').textContent = data.payments_today || 0;
    } catch (error) {
        console.error('Error loading dashboard:', error);
    }
}

// Load users list
async function loadUsers(filter = '') {
    const list = document.getElementById('usersList');
    list.innerHTML = '<div class="loading">Loading...</div>';

    try {
        const url = filter ? `${API_URL}/admin/users?status=${filter}` : `${API_URL}/admin/users`;
        const response = await fetch(url, {
            headers: {
                'Authorization': `Bearer ${ADMIN_TOKEN}`
            }
        });
        const data = await response.json();

        if (data.users.length === 0) {
            list.innerHTML = '<div class="loading">No users found</div>';
            return;
        }

        list.innerHTML = data.users.map(user => `
            <div class="list-item" onclick="showUserDetails(${user.id})" style="cursor: pointer;">
                <div class="list-item-header">
                    <div class="list-item-username">@${user.username || user.tg_user_id}</div>
                    <div class="list-item-badge ${user.has_subscription ? 'badge-paid' : (user.is_blocked ? 'badge-blocked' : 'badge-active')}">
                        ${user.has_subscription ? 'PAID' : (user.is_blocked ? 'BLOCKED' : 'FREE')}
                    </div>
                </div>
                <div class="list-item-details">
                    <div class="detail-row">
                        <div class="detail-label">User ID</div>
                        <div class="detail-value">${user.tg_user_id}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-label">Questions Left</div>
                        <div class="detail-value">${user.free_questions_left}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-label">First Seen</div>
                        <div class="detail-value">${formatDate(user.first_seen_at)}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-label">Last Seen</div>
                        <div class="detail-value">${formatDate(user.last_seen_at)}</div>
                    </div>
                </div>
                ${user.subscription_end ? `
                    <div class="detail-row" style="margin-top: 8px">
                        <div class="detail-label">Subscription Ends</div>
                        <div class="detail-value">${formatDate(user.subscription_end)}</div>
                    </div>
                ` : ''}
            </div>
        `).join('');
    } catch (error) {
        list.innerHTML = '<div class="error">Error loading users</div>';
        console.error('Error loading users:', error);
    }
}

// Load subscriptions list
async function loadSubscriptions(filter = '') {
    const list = document.getElementById('subscriptionsList');
    list.innerHTML = '<div class="loading">Loading...</div>';

    try {
        const url = filter ? `${API_URL}/admin/subscriptions?status=${filter}` : `${API_URL}/admin/subscriptions`;
        const response = await fetch(url, {
            headers: {
                'Authorization': `Bearer ${ADMIN_TOKEN}`
            }
        });
        const data = await response.json();

        if (data.subscriptions.length === 0) {
            list.innerHTML = '<div class="loading">No subscriptions found</div>';
            return;
        }

        list.innerHTML = data.subscriptions.map(sub => `
            <div class="sub-item">
                <div class="sub-header">
                    <div class="sub-user">@${sub.username || sub.tg_user_id}</div>
                    <div class="sub-amount">${sub.amount.toFixed(0)} ${sub.currency}</div>
                </div>
                <div class="sub-details">
                    <span class="sub-plan">${sub.plan_code}</span>
                    <span style="opacity: 0.6; font-size: 12px">${formatDate(sub.started_at)} → ${formatDate(sub.ends_at)}</span>
                </div>
            </div>
        `).join('');
    } catch (error) {
        list.innerHTML = '<div class="error">Error loading subscriptions</div>';
        console.error('Error loading subscriptions:', error);
    }
}

// Format date
function formatDate(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays}d ago`;

    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// Tab switching
document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

        tab.classList.add('active');
        document.getElementById(`${tab.dataset.tab}-tab`).classList.add('active');

        if (tab.dataset.tab === 'users') {
            loadUsers(currentUserFilter);
        } else if (tab.dataset.tab === 'subscriptions') {
            loadSubscriptions(currentSubFilter);
        } else if (tab.dataset.tab === 'events') {
            loadEvents();
        } else if (tab.dataset.tab === 'tasks') {
            loadTasks();
        } else if (tab.dataset.tab === 'templates') {
            loadTemplates();
        } else if (tab.dataset.tab === 'daily-messages') {
            loadDailyMessages();
        } else if (tab.dataset.tab === 'prompts') {
            loadPrompts(currentPromptFilter);
        }
    });
});

// User filters
document.querySelectorAll('[data-filter]').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('[data-filter]').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        currentUserFilter = btn.dataset.filter;
        loadUsers(currentUserFilter);
    });
});

// Subscription filters
document.querySelectorAll('[data-filter-sub]').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('[data-filter-sub]').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        currentSubFilter = btn.dataset.filterSub;
        loadSubscriptions(currentSubFilter);
    });
});

// CRM Test handler
document.getElementById('testCrmBtn').addEventListener('click', async () => {
    const btn = document.getElementById('testCrmBtn');
    const resultsDiv = document.getElementById('crmTestResults');

    btn.disabled = true;
    btn.textContent = '⏳ Тестируем...';
    resultsDiv.style.display = 'none';

    try {
        const url = CURRENT_USER_TG_ID
            ? `${API_URL}/admin/test/crm?tg_user_id=${CURRENT_USER_TG_ID}`
            : `${API_URL}/admin/test/crm`;

        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${ADMIN_TOKEN}`
            }
        });

        const data = await response.json();

        if (data.status === 'success') {
            resultsDiv.innerHTML = `
                <h4 class="success">✅ CRM Тест Успешно</h4>
                <div class="result-item">
                    <strong>Admin ID:</strong> ${data.admin_id}
                </div>
                <div class="result-item">
                    <strong>Создано задач:</strong> ${data.tasks_created}
                    <br>
                    <strong>Время выполнения:</strong> ${new Date(data.due_at_utc).toLocaleString()}
                    <br>
                    <strong>Текущее время:</strong> ${new Date(data.current_time_utc).toLocaleString()}
                    <br><br>
                    ${data.tasks.map(t =>
                        `<div style="margin-left: 10px; margin-top: 5px;">• ${t.type} (ID: ${t.id}) - ${t.status}</div>`
                    ).join('')}
                </div>
                <div class="result-item" style="margin-top: 10px; color: #666; font-size: 13px;">
                    ℹ️ Задачи будут отправлены автоматически через ~1 минуту
                </div>
            `;
            resultsDiv.style.display = 'block';
        } else {
            resultsDiv.innerHTML = `
                <h4 class="error">❌ Ошибка теста</h4>
                <div class="result-item">${data.message || 'Unknown error'}</div>
            `;
            resultsDiv.style.display = 'block';
        }
    } catch (error) {
        console.error('Error testing CRM:', error);
        resultsDiv.innerHTML = `
            <h4 class="error">❌ Ошибка</h4>
            <div class="result-item">${error.message}</div>
        `;
        resultsDiv.style.display = 'block';
    } finally {
        btn.disabled = false;
        btn.textContent = '🧪 Тест CRM';
    }
});

// Show user details modal
async function showUserDetails(userId) {
    const modal = document.getElementById('userModal');
    const modalBody = document.getElementById('userModalBody');

    modal.style.display = 'flex';
    modalBody.innerHTML = '<div class="loading">Loading user details...</div>';

    try {
        const response = await fetch(`${API_URL}/admin/users/${userId}`, {
            headers: {
                'Authorization': `Bearer ${ADMIN_TOKEN}`
            }
        });
        const data = await response.json();

        const user = data.user;

        modalBody.innerHTML = `
            <div class="modal-section">
                <h3>👤 User Info</h3>
                <div class="modal-info">
                    <div><strong>Username:</strong> @${user.username || user.tg_user_id}</div>
                    <div><strong>Age:</strong> ${user.age || '-'}</div>
                    <div><strong>Gender:</strong> ${user.gender || '-'}</div>
                    <div><strong>Free Questions:</strong> ${user.free_questions_left}</div>
                    <div><strong>Subscription:</strong> ${user.has_subscription ? `Active until ${formatDate(user.subscription_end)}` : 'None'}</div>
                    ${user.admin_thread_id || user.oracle_thread_id ? `
                        <div style="margin-top: 12px; padding: 12px; background: var(--tg-theme-secondary-bg-color, #f0f0f0); border-radius: 6px; border-left: 4px solid var(--tg-theme-button-color, #3390ec);">
                            <strong>🧠 AI Sessions:</strong>
                            ${user.admin_thread_id ? `
                                <div style="margin-top: 6px; font-size: 12px;">
                                    <strong>🎭 Admin:</strong> <code style="font-size: 11px; opacity: 0.7;">${user.admin_thread_id}</code>
                                </div>
                            ` : ''}
                            ${user.oracle_thread_id ? `
                                <div style="margin-top: 6px; font-size: 12px;">
                                    <strong>🔮 Oracle:</strong> <code style="font-size: 11px; opacity: 0.7;">${user.oracle_thread_id}</code>
                                </div>
                            ` : ''}
                        </div>
                    ` : ''}
                </div>

                <div style="display: flex; gap: 8px; margin-top: 16px;">
                    <button onclick="addPremiumDay(${user.id})" class="test-crm-btn" style="flex: 1; background: #4CAF50;">
                        💎 +1 Day Premium
                    </button>
                    <button onclick="deleteUser(${user.id}, ${user.tg_user_id})" class="test-crm-btn" style="flex: 1; background: #f44336;">
                        🗑️ Delete User
                    </button>
                </div>
            </div>

            <div class="modal-section">
                <h3>📨 Daily Messages (${data.daily_messages.length})</h3>
                <div class="modal-list">
                    ${data.daily_messages.length > 0 ? data.daily_messages.map(msg => `
                        <div class="modal-list-item">
                            <span>${formatDate(msg.date)}</span>
                        </div>
                    `).join('') : '<div class="empty">No daily messages yet</div>'}
                </div>
            </div>

            <div class="modal-section">
                <h3>🔮 Oracle Questions (${data.oracle_questions.length})</h3>
                <div class="modal-list">
                    ${data.oracle_questions.length > 0 ? data.oracle_questions.slice(0, 10).map(q => `
                        <div class="modal-list-item">
                            <div class="modal-question"><strong>Q:</strong> ${q.question}</div>
                            <div class="modal-answer"><strong>A:</strong> ${q.answer.substring(0, 100)}${q.answer.length > 100 ? '...' : ''}</div>
                            <div class="modal-meta">${q.source} • ${formatDate(q.date)} • ${q.tokens} tokens</div>
                        </div>
                    `).join('') : '<div class="empty">No questions asked yet</div>'}
                </div>
            </div>

            <div class="modal-section">
                <h3>💳 Payments (${data.payments.length})</h3>
                <div class="modal-list">
                    ${data.payments.length > 0 ? data.payments.map(p => `
                        <div class="modal-list-item">
                            <span><strong>${p.plan}:</strong> ${p.amount}₽</span>
                            <span class="badge-${p.status === 'success' ? 'active' : 'blocked'}">${p.status}</span>
                            <span>${formatDate(p.paid_at || p.created_at)}</span>
                        </div>
                    `).join('') : '<div class="empty">No payments yet</div>'}
                </div>
            </div>

            <div class="modal-section">
                <h3>🤖 CRM Logs (${data.crm_logs.length})</h3>
                <div class="modal-list">
                    ${data.crm_logs.length > 0 ? data.crm_logs.slice(0, 20).map(log => `
                        <div class="modal-list-item">
                            <span><strong>${log.type}:</strong> ${log.status}</span>
                            ${log.result_code ? `<span class="error">${log.result_code}</span>` : ''}
                            <span>${formatDate(log.sent_at || log.due_at || log.created_at)}</span>
                        </div>
                    `).join('') : '<div class="empty">No CRM activity yet</div>'}
                </div>
            </div>
        `;
    } catch (error) {
        console.error('Error loading user details:', error);
        modalBody.innerHTML = '<div class="error">Error loading user details</div>';
    }
}

// Delete user
async function deleteUser(userId, tgUserId) {
    if (!confirm(`Are you sure you want to DELETE user @${tgUserId}?\n\nThis will:\n- Remove all user data\n- Reset counters\n- Allow them to register again\n\nThis action cannot be undone!`)) {
        return;
    }

    try {
        const response = await fetch(`${API_URL}/admin/users/${userId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${ADMIN_TOKEN}`
            }
        });

        const data = await response.json();

        if (response.ok) {
            alert(`✅ ${data.message}`);
            closeUserModal();
            loadUsers(currentUserFilter);
            loadDashboard();
        } else {
            alert(`❌ Error: ${data.detail || 'Failed to delete user'}`);
        }
    } catch (error) {
        console.error('Error deleting user:', error);
        alert('❌ Error deleting user');
    }
}

// Add premium day
async function addPremiumDay(userId) {
    if (!confirm('Add 1 day premium subscription to this user?')) {
        return;
    }

    try {
        const response = await fetch(`${API_URL}/admin/users/${userId}/premium`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${ADMIN_TOKEN}`
            }
        });

        const data = await response.json();

        if (response.ok) {
            alert(`✅ ${data.message}\nEnds: ${formatDate(data.subscription_end)}`);
            // Reload user details
            showUserDetails(userId);
            loadDashboard();
        } else {
            alert(`❌ Error: ${data.detail || 'Failed to add premium'}`);
        }
    } catch (error) {
        console.error('Error adding premium:', error);
        alert('❌ Error adding premium');
    }
}

// Close modal
function closeUserModal() {
    document.getElementById('userModal').style.display = 'none';
}

// Load events list
async function loadEvents() {
    const list = document.getElementById('eventsList');
    list.innerHTML = '<div class="loading">Loading...</div>';

    try {
        const response = await fetch(`${API_URL}/admin/events?limit=100`, {
            headers: {
                'Authorization': `Bearer ${ADMIN_TOKEN}`
            }
        });
        const data = await response.json();

        if (data.events.length === 0) {
            list.innerHTML = '<div class="loading">No events found</div>';
            return;
        }

        list.innerHTML = data.events.map(event => `
            <div class="list-item">
                <div class="list-item-header">
                    <div class="list-item-username">${event.type}</div>
                    <div style="display: flex; gap: 8px;">
                        <button onclick="editEvent(${event.id})" style="padding: 4px 12px; background: #3390ec; color: white; border: none; border-radius: 6px; font-size: 12px; cursor: pointer;">Edit</button>
                        <button onclick="deleteEvent(${event.id})" style="padding: 4px 12px; background: #f44336; color: white; border: none; border-radius: 6px; font-size: 12px; cursor: pointer;">Delete</button>
                    </div>
                </div>
                <div class="list-item-details">
                    <div class="detail-row">
                        <div class="detail-label">Event ID</div>
                        <div class="detail-value">${event.id}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-label">User</div>
                        <div class="detail-value">${event.username ? '@' + event.username : event.user_id || 'N/A'}</div>
                    </div>
                    <div class="detail-row" style="grid-column: 1 / -1;">
                        <div class="detail-label">Meta</div>
                        <div class="detail-value" style="font-family: monospace; font-size: 11px; word-break: break-all;">${JSON.stringify(event.meta)}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-label">Occurred At</div>
                        <div class="detail-value">${formatDate(event.occurred_at)}</div>
                    </div>
                </div>
            </div>
        `).join('');
    } catch (error) {
        list.innerHTML = '<div class="error">Error loading events</div>';
        console.error('Error loading events:', error);
    }
}

// Create event button handler
document.getElementById('createEventBtn').addEventListener('click', () => {
    document.getElementById('eventModalTitle').textContent = 'Create Event';
    document.getElementById('eventForm').reset();
    document.getElementById('eventId').value = '';
    document.getElementById('eventModal').style.display = 'flex';
});

// Event form submit handler
document.getElementById('eventForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const eventId = document.getElementById('eventId').value;
    const userId = document.getElementById('eventUserId').value;
    const type = document.getElementById('eventType').value;
    const metaStr = document.getElementById('eventMeta').value;

    let meta = {};
    if (metaStr.trim()) {
        try {
            meta = JSON.parse(metaStr);
        } catch (err) {
            alert('Invalid JSON in Meta field');
            return;
        }
    }

    const payload = {
        user_id: userId ? parseInt(userId) : null,
        type: type,
        meta: meta
    };

    try {
        const url = eventId ? `${API_URL}/admin/events/${eventId}` : `${API_URL}/admin/events`;
        const method = eventId ? 'PUT' : 'POST';

        const response = await fetch(url, {
            method: method,
            headers: {
                'Authorization': `Bearer ${ADMIN_TOKEN}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        const result = await response.json();

        if (response.ok) {
            closeEventModal();
            loadEvents();
        } else {
            alert(`Error: ${result.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error saving event:', error);
        alert('Error saving event');
    }
});

// Edit event
async function editEvent(eventId) {
    try {
        const response = await fetch(`${API_URL}/admin/events?limit=500`, {
            headers: {
                'Authorization': `Bearer ${ADMIN_TOKEN}`
            }
        });
        const data = await response.json();
        const event = data.events.find(e => e.id === eventId);

        if (event) {
            document.getElementById('eventModalTitle').textContent = 'Edit Event';
            document.getElementById('eventId').value = event.id;
            document.getElementById('eventUserId').value = event.user_id || '';
            document.getElementById('eventType').value = event.type;
            document.getElementById('eventMeta').value = JSON.stringify(event.meta, null, 2);
            document.getElementById('eventModal').style.display = 'flex';
        }
    } catch (error) {
        console.error('Error loading event:', error);
        alert('Error loading event');
    }
}

// Delete event
async function deleteEvent(eventId) {
    if (!confirm('Are you sure you want to delete this event?')) {
        return;
    }

    try {
        const response = await fetch(`${API_URL}/admin/events/${eventId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${ADMIN_TOKEN}`
            }
        });

        if (response.ok) {
            loadEvents();
        } else {
            const result = await response.json();
            alert(`Error: ${result.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error deleting event:', error);
        alert('Error deleting event');
    }
}

// Close event modal
function closeEventModal() {
    document.getElementById('eventModal').style.display = 'none';
}

// ============================================================================
// Admin Tasks CRUD
// ============================================================================

// Load tasks list
async function loadTasks() {
    const list = document.getElementById('tasksList');
    list.innerHTML = '<div class="loading">Loading...</div>';

    try {
        const response = await fetch(`${API_URL}/admin/tasks?limit=100`, {
            headers: {
                'Authorization': `Bearer ${ADMIN_TOKEN}`
            }
        });
        const data = await response.json();

        if (data.tasks.length === 0) {
            list.innerHTML = '<div class="loading">No tasks found</div>';
            return;
        }

        list.innerHTML = data.tasks.map(task => `
            <div class="list-item">
                <div class="list-item-header">
                    <div class="list-item-username">${task.type}</div>
                    <div style="display: flex; gap: 8px; align-items: center;">
                        <span class="list-item-badge ${task.status === 'sent' ? 'badge-active' : (task.status === 'failed' ? 'badge-blocked' : 'badge-paid')}">${task.status.toUpperCase()}</span>
                        <button onclick="editTask(${task.id})" style="padding: 4px 12px; background: #3390ec; color: white; border: none; border-radius: 6px; font-size: 12px; cursor: pointer;">Edit</button>
                        <button onclick="deleteTask(${task.id})" style="padding: 4px 12px; background: #f44336; color: white; border: none; border-radius: 6px; font-size: 12px; cursor: pointer;">Delete</button>
                    </div>
                </div>
                <div class="list-item-details">
                    <div class="detail-row">
                        <div class="detail-label">Task ID</div>
                        <div class="detail-value">${task.id}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-label">User</div>
                        <div class="detail-value">${task.username ? '@' + task.username : task.user_id || 'N/A'}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-label">Due At</div>
                        <div class="detail-value">${task.due_at ? formatDate(task.due_at) : '-'}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-label">Sent At</div>
                        <div class="detail-value">${task.sent_at ? formatDate(task.sent_at) : '-'}</div>
                    </div>
                    <div class="detail-row" style="grid-column: 1 / -1;">
                        <div class="detail-label">Payload</div>
                        <div class="detail-value" style="font-family: monospace; font-size: 11px; word-break: break-all;">${JSON.stringify(task.payload)}</div>
                    </div>
                    ${task.result_code ? `
                        <div class="detail-row" style="grid-column: 1 / -1;">
                            <div class="detail-label">Result Code</div>
                            <div class="detail-value" style="color: #f44336;">${task.result_code}</div>
                        </div>
                    ` : ''}
                </div>
            </div>
        `).join('');
    } catch (error) {
        list.innerHTML = '<div class="error">Error loading tasks</div>';
        console.error('Error loading tasks:', error);
    }
}

// Create task button handler
document.getElementById('createTaskBtn').addEventListener('click', () => {
    document.getElementById('taskModalTitle').textContent = 'Create Task';
    document.getElementById('taskForm').reset();
    document.getElementById('taskId').value = '';
    document.getElementById('taskModal').style.display = 'flex';
});

// Task form submit handler
document.getElementById('taskForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const taskId = document.getElementById('taskId').value;
    const userId = document.getElementById('taskUserId').value;
    const type = document.getElementById('taskType').value;
    const status = document.getElementById('taskStatus').value;
    const payloadStr = document.getElementById('taskPayload').value;
    const scheduledAt = document.getElementById('taskScheduledAt').value;
    const dueAt = document.getElementById('taskDueAt').value;

    let payload = {};
    if (payloadStr.trim()) {
        try {
            payload = JSON.parse(payloadStr);
        } catch (err) {
            alert('Invalid JSON in Payload field');
            return;
        }
    }

    const data = {
        user_id: userId ? parseInt(userId) : null,
        type: type,
        status: status,
        payload: payload,
        scheduled_at: scheduledAt || null,
        due_at: dueAt || null
    };

    try {
        const url = taskId ? `${API_URL}/admin/tasks/${taskId}` : `${API_URL}/admin/tasks`;
        const method = taskId ? 'PUT' : 'POST';

        const response = await fetch(url, {
            method: method,
            headers: {
                'Authorization': `Bearer ${ADMIN_TOKEN}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (response.ok) {
            closeTaskModal();
            loadTasks();
        } else {
            alert(`Error: ${result.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error saving task:', error);
        alert('Error saving task');
    }
});

// Edit task
async function editTask(taskId) {
    try {
        const response = await fetch(`${API_URL}/admin/tasks?limit=500`, {
            headers: {
                'Authorization': `Bearer ${ADMIN_TOKEN}`
            }
        });
        const data = await response.json();
        const task = data.tasks.find(t => t.id === taskId);

        if (task) {
            document.getElementById('taskModalTitle').textContent = 'Edit Task';
            document.getElementById('taskId').value = task.id;
            document.getElementById('taskUserId').value = task.user_id || '';
            document.getElementById('taskType').value = task.type;
            document.getElementById('taskStatus').value = task.status;
            document.getElementById('taskPayload').value = JSON.stringify(task.payload, null, 2);

            // Convert ISO to datetime-local format
            if (task.scheduled_at) {
                document.getElementById('taskScheduledAt').value = task.scheduled_at.substring(0, 16);
            }
            if (task.due_at) {
                document.getElementById('taskDueAt').value = task.due_at.substring(0, 16);
            }

            document.getElementById('taskModal').style.display = 'flex';
        }
    } catch (error) {
        console.error('Error loading task:', error);
        alert('Error loading task');
    }
}

// Delete task
async function deleteTask(taskId) {
    if (!confirm('Are you sure you want to delete this task?')) {
        return;
    }

    try {
        const response = await fetch(`${API_URL}/admin/tasks/${taskId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${ADMIN_TOKEN}`
            }
        });

        if (response.ok) {
            loadTasks();
        } else {
            const result = await response.json();
            alert(`Error: ${result.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error deleting task:', error);
        alert('Error deleting task');
    }
}

// Close task modal
function closeTaskModal() {
    document.getElementById('taskModal').style.display = 'none';
}

// ============================================================================
// Admin Templates CRUD
// ============================================================================

// Load templates list
async function loadTemplates() {
    const list = document.getElementById('templatesList');
    list.innerHTML = '<div class="loading">Loading...</div>';

    try {
        const response = await fetch(`${API_URL}/admin/templates`, {
            headers: {
                'Authorization': `Bearer ${ADMIN_TOKEN}`
            }
        });
        const data = await response.json();

        if (data.templates.length === 0) {
            list.innerHTML = '<div class="loading">No templates found</div>';
            return;
        }

        list.innerHTML = data.templates.map(template => `
            <div class="list-item">
                <div class="list-item-header">
                    <div class="list-item-username">${template.type} - ${template.tone}</div>
                    <div style="display: flex; gap: 8px; align-items: center;">
                        <span class="list-item-badge ${template.enabled ? 'badge-active' : 'badge-blocked'}">${template.enabled ? 'ENABLED' : 'DISABLED'}</span>
                        <button onclick="editTemplate(${template.id})" style="padding: 4px 12px; background: #3390ec; color: white; border: none; border-radius: 6px; font-size: 12px; cursor: pointer;">Edit</button>
                        <button onclick="deleteTemplate(${template.id})" style="padding: 4px 12px; background: #f44336; color: white; border: none; border-radius: 6px; font-size: 12px; cursor: pointer;">Delete</button>
                    </div>
                </div>
                <div class="list-item-details">
                    <div class="detail-row">
                        <div class="detail-label">Template ID</div>
                        <div class="detail-value">${template.id}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-label">Weight</div>
                        <div class="detail-value">${template.weight}</div>
                    </div>
                    <div class="detail-row" style="grid-column: 1 / -1;">
                        <div class="detail-label">Text</div>
                        <div class="detail-value" style="word-break: break-word;">${template.text.substring(0, 150)}${template.text.length > 150 ? '...' : ''}</div>
                    </div>
                </div>
            </div>
        `).join('');
    } catch (error) {
        list.innerHTML = '<div class="error">Error loading templates</div>';
        console.error('Error loading templates:', error);
    }
}

// Create template button handler
document.getElementById('createTemplateBtn').addEventListener('click', () => {
    document.getElementById('templateModalTitle').textContent = 'Create Template';
    document.getElementById('templateForm').reset();
    document.getElementById('templateId').value = '';
    document.getElementById('templateEnabled').checked = true;
    document.getElementById('templateWeight').value = '10';
    document.getElementById('templateModal').style.display = 'flex';
});

// Template form submit handler
document.getElementById('templateForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const templateId = document.getElementById('templateId').value;
    const type = document.getElementById('templateType').value;
    const tone = document.getElementById('templateTone').value;
    const text = document.getElementById('templateText').value;
    const enabled = document.getElementById('templateEnabled').checked;
    const weight = parseInt(document.getElementById('templateWeight').value);

    const payload = {
        type: type,
        tone: tone,
        text: text,
        enabled: enabled,
        weight: weight
    };

    try {
        const url = templateId ? `${API_URL}/admin/templates/${templateId}` : `${API_URL}/admin/templates`;
        const method = templateId ? 'PUT' : 'POST';

        const response = await fetch(url, {
            method: method,
            headers: {
                'Authorization': `Bearer ${ADMIN_TOKEN}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        const result = await response.json();

        if (response.ok) {
            closeTemplateModal();
            loadTemplates();
        } else {
            alert(`Error: ${result.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error saving template:', error);
        alert('Error saving template');
    }
});

// Edit template
async function editTemplate(templateId) {
    try {
        const response = await fetch(`${API_URL}/admin/templates`, {
            headers: {
                'Authorization': `Bearer ${ADMIN_TOKEN}`
            }
        });
        const data = await response.json();
        const template = data.templates.find(t => t.id === templateId);

        if (template) {
            document.getElementById('templateModalTitle').textContent = 'Edit Template';
            document.getElementById('templateId').value = template.id;
            document.getElementById('templateType').value = template.type;
            document.getElementById('templateTone').value = template.tone;
            document.getElementById('templateText').value = template.text;
            document.getElementById('templateEnabled').checked = template.enabled;
            document.getElementById('templateWeight').value = template.weight;
            document.getElementById('templateModal').style.display = 'flex';
        }
    } catch (error) {
        console.error('Error loading template:', error);
        alert('Error loading template');
    }
}

// Delete template
async function deleteTemplate(templateId) {
    if (!confirm('Are you sure you want to delete this template?')) {
        return;
    }

    try {
        const response = await fetch(`${API_URL}/admin/templates/${templateId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${ADMIN_TOKEN}`
            }
        });

        if (response.ok) {
            loadTemplates();
        } else {
            const result = await response.json();
            alert(`Error: ${result.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error deleting template:', error);
        alert('Error deleting template');
    }
}

// Close template modal
function closeTemplateModal() {
    document.getElementById('templateModal').style.display = 'none';
}

// ============================================================================
// Daily Messages CRUD
// ============================================================================

// Load daily messages list
async function loadDailyMessages() {
    const list = document.getElementById('dailyMessagesList');
    list.innerHTML = '<div class="loading">Loading...</div>';

    try {
        const response = await fetch(`${API_URL}/admin/daily-messages`, {
            headers: {
                'Authorization': `Bearer ${ADMIN_TOKEN}`
            }
        });
        const data = await response.json();

        if (data.messages.length === 0) {
            list.innerHTML = '<div class="loading">No daily messages found</div>';
            return;
        }

        list.innerHTML = data.messages.map(message => `
            <div class="list-item">
                <div class="list-item-header">
                    <div class="list-item-username">Message #${message.id}</div>
                    <div style="display: flex; gap: 8px; align-items: center;">
                        <span class="list-item-badge ${message.is_active ? 'badge-active' : 'badge-blocked'}">${message.is_active ? 'ACTIVE' : 'INACTIVE'}</span>
                        <button onclick="editDailyMessage(${message.id})" style="padding: 4px 12px; background: #3390ec; color: white; border: none; border-radius: 6px; font-size: 12px; cursor: pointer;">Edit</button>
                        <button onclick="deleteDailyMessage(${message.id})" style="padding: 4px 12px; background: #f44336; color: white; border: none; border-radius: 6px; font-size: 12px; cursor: pointer;">Delete</button>
                    </div>
                </div>
                <div class="list-item-details">
                    <div class="detail-row">
                        <div class="detail-label">Message ID</div>
                        <div class="detail-value">${message.id}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-label">Weight</div>
                        <div class="detail-value">${message.weight}</div>
                    </div>
                    <div class="detail-row" style="grid-column: 1 / -1;">
                        <div class="detail-label">Text</div>
                        <div class="detail-value" style="word-break: break-word;">${message.text.substring(0, 100)}${message.text.length > 100 ? '...' : ''}</div>
                    </div>
                </div>
            </div>
        `).join('');
    } catch (error) {
        list.innerHTML = '<div class="error">Error loading daily messages</div>';
        console.error('Error loading daily messages:', error);
    }
}

// Create daily message button handler
document.getElementById('createDailyMsgBtn').addEventListener('click', () => {
    document.getElementById('dailyMessageModalTitle').textContent = 'Create Daily Message';
    document.getElementById('dailyMessageForm').reset();
    document.getElementById('dailyMessageId').value = '';
    document.getElementById('dailyMessageActive').checked = true;
    document.getElementById('dailyMessageWeight').value = '10';
    document.getElementById('dailyMessageModal').style.display = 'flex';
});

// Daily message form submit handler
document.getElementById('dailyMessageForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const messageId = document.getElementById('dailyMessageId').value;
    const text = document.getElementById('dailyMessageText').value;
    const isActive = document.getElementById('dailyMessageActive').checked;
    const weight = parseInt(document.getElementById('dailyMessageWeight').value);

    const payload = {
        text: text,
        is_active: isActive,
        weight: weight
    };

    try {
        const url = messageId ? `${API_URL}/admin/daily-messages/${messageId}` : `${API_URL}/admin/daily-messages`;
        const method = messageId ? 'PUT' : 'POST';

        const response = await fetch(url, {
            method: method,
            headers: {
                'Authorization': `Bearer ${ADMIN_TOKEN}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        const result = await response.json();

        if (response.ok) {
            closeDailyMessageModal();
            loadDailyMessages();
        } else {
            alert(`Error: ${result.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error saving daily message:', error);
        alert('Error saving daily message');
    }
});

// Edit daily message
async function editDailyMessage(messageId) {
    try {
        const response = await fetch(`${API_URL}/admin/daily-messages`, {
            headers: {
                'Authorization': `Bearer ${ADMIN_TOKEN}`
            }
        });
        const data = await response.json();
        const message = data.messages.find(m => m.id === messageId);

        if (message) {
            document.getElementById('dailyMessageModalTitle').textContent = 'Edit Daily Message';
            document.getElementById('dailyMessageId').value = message.id;
            document.getElementById('dailyMessageText').value = message.text;
            document.getElementById('dailyMessageActive').checked = message.is_active;
            document.getElementById('dailyMessageWeight').value = message.weight;
            document.getElementById('dailyMessageModal').style.display = 'flex';
        }
    } catch (error) {
        console.error('Error loading daily message:', error);
        alert('Error loading daily message');
    }
}

// Delete daily message
async function deleteDailyMessage(messageId) {
    if (!confirm('Are you sure you want to delete this daily message?')) {
        return;
    }

    try {
        const response = await fetch(`${API_URL}/admin/daily-messages/${messageId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${ADMIN_TOKEN}`
            }
        });

        if (response.ok) {
            loadDailyMessages();
        } else {
            const result = await response.json();
            alert(`Error: ${result.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error deleting daily message:', error);
        alert('Error deleting daily message');
    }
}

// Close daily message modal
function closeDailyMessageModal() {
    document.getElementById('dailyMessageModal').style.display = 'none';
}

// ============================================================================
// AI Prompts CRUD
// ============================================================================

// Current prompt filter
let currentPromptFilter = '';

// Load prompts list
async function loadPrompts(isActiveFilter = '') {
    const list = document.getElementById('promptsList');
    list.innerHTML = '<div class="loading">Loading...</div>';

    try {
        let url = `${API_URL}/admin/prompts?limit=100`;
        if (isActiveFilter !== '') {
            url += `&is_active=${isActiveFilter}`;
        }

        const response = await fetch(url, {
            headers: {
                'Authorization': `Bearer ${ADMIN_TOKEN}`
            }
        });
        const data = await response.json();

        if (data.prompts.length === 0) {
            list.innerHTML = '<div class="loading">No prompts found</div>';
            return;
        }

        list.innerHTML = data.prompts.map(prompt => `
            <div class="list-item">
                <div class="list-item-header">
                    <div class="list-item-username">${prompt.name}</div>
                    <div style="display: flex; gap: 8px; align-items: center;">
                        <span class="list-item-badge ${prompt.is_active ? 'badge-active' : 'badge-blocked'}">${prompt.is_active ? 'ACTIVE' : 'INACTIVE'}</span>
                        <button onclick="editPrompt(${prompt.id})" style="padding: 4px 12px; background: #3390ec; color: white; border: none; border-radius: 6px; font-size: 12px; cursor: pointer;">Edit</button>
                        <button onclick="deletePrompt(${prompt.id})" style="padding: 4px 12px; background: #f44336; color: white; border: none; border-radius: 6px; font-size: 12px; cursor: pointer;">Delete</button>
                    </div>
                </div>
                <div class="list-item-details">
                    <div class="detail-row">
                        <div class="detail-label">ID</div>
                        <div class="detail-value">${prompt.id}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-label">Key</div>
                        <div class="detail-value">${prompt.key}</div>
                    </div>
                    <div class="detail-row" style="grid-column: 1 / -1;">
                        <div class="detail-label">Description</div>
                        <div class="detail-value">${prompt.description || 'N/A'}</div>
                    </div>
                    <div class="detail-row" style="grid-column: 1 / -1;">
                        <div class="detail-label">Prompt Text</div>
                        <div class="detail-value" style="word-break: break-word; font-family: monospace; font-size: 12px;">${prompt.prompt_text.substring(0, 150)}${prompt.prompt_text.length > 150 ? '...' : ''}</div>
                    </div>
                </div>
            </div>
        `).join('');
    } catch (error) {
        list.innerHTML = '<div class="error">Error loading prompts</div>';
        console.error('Error loading prompts:', error);
    }
}

// Prompt filter buttons
document.querySelectorAll('[data-filter-prompt]').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('[data-filter-prompt]').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentPromptFilter = btn.dataset.filterPrompt;
        loadPrompts(currentPromptFilter);
    });
});

// Create prompt button handler
document.getElementById('createPromptBtn').addEventListener('click', () => {
    document.getElementById('promptModalTitle').textContent = 'Create AI Prompt';
    document.getElementById('promptForm').reset();
    document.getElementById('promptId').value = '';
    document.getElementById('promptActive').checked = true;
    document.getElementById('promptModal').style.display = 'flex';
});

// Prompt form submit handler
document.getElementById('promptForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const promptId = document.getElementById('promptId').value;
    const key = document.getElementById('promptKey').value;
    const name = document.getElementById('promptName').value;
    const description = document.getElementById('promptDescription').value;
    const promptText = document.getElementById('promptText').value;
    const isActive = document.getElementById('promptActive').checked;

    const payload = {
        key: key,
        name: name,
        prompt_text: promptText,
        description: description || null,
        is_active: isActive
    };

    try {
        const url = promptId ? `${API_URL}/admin/prompts/${promptId}` : `${API_URL}/admin/prompts`;
        const method = promptId ? 'PUT' : 'POST';

        const response = await fetch(url, {
            method: method,
            headers: {
                'Authorization': `Bearer ${ADMIN_TOKEN}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        const result = await response.json();

        if (response.ok) {
            closePromptModal();
            loadPrompts(currentPromptFilter);
        } else {
            alert(`Error: ${result.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error saving prompt:', error);
        alert('Error saving prompt');
    }
});

// Edit prompt
async function editPrompt(promptId) {
    try {
        const response = await fetch(`${API_URL}/admin/prompts/${promptId}`, {
            headers: {
                'Authorization': `Bearer ${ADMIN_TOKEN}`
            }
        });
        const prompt = await response.json();

        if (prompt) {
            document.getElementById('promptModalTitle').textContent = 'Edit AI Prompt';
            document.getElementById('promptId').value = prompt.id;
            document.getElementById('promptKey').value = prompt.key;
            document.getElementById('promptName').value = prompt.name;
            document.getElementById('promptDescription').value = prompt.description || '';
            document.getElementById('promptText').value = prompt.prompt_text;
            document.getElementById('promptActive').checked = prompt.is_active;
            document.getElementById('promptModal').style.display = 'flex';
        }
    } catch (error) {
        console.error('Error loading prompt:', error);
        alert('Error loading prompt');
    }
}

// Delete prompt
async function deletePrompt(promptId) {
    if (!confirm('Are you sure you want to delete this prompt?')) {
        return;
    }

    try {
        const response = await fetch(`${API_URL}/admin/prompts/${promptId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${ADMIN_TOKEN}`
            }
        });

        if (response.ok) {
            loadPrompts(currentPromptFilter);
        } else {
            const result = await response.json();
            alert(`Error: ${result.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error deleting prompt:', error);
        alert('Error deleting prompt');
    }
}

// Close prompt modal
function closePromptModal() {
    document.getElementById('promptModal').style.display = 'none';
}

// Load AI sessions
async function loadSessions() {
    try {
        const response = await fetch(`${API_URL}/admin/sessions`, {
            headers: {
                'Authorization': `Bearer ${ADMIN_TOKEN}`
            }
        });
        const data = await response.json();

        const sessionsList = document.getElementById('sessionsList');

        if (!data.sessions || data.sessions.length === 0) {
            sessionsList.innerHTML = '<div class="empty-state">No active AI sessions</div>';
            return;
        }

        let html = '';
        data.sessions.forEach(session => {
            const threadsHtml = session.threads.map(t => {
                const personaEmoji = t.persona === 'admin' ? '🎭' : '🔮';
                return `
                    <div style="margin-top: 8px; padding: 8px; background: var(--tg-theme-bg-color, #fff); border-radius: 6px; border-left: 3px solid var(--tg-theme-button-color, #3390ec);">
                        <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
                            <span style="font-size: 16px;">${personaEmoji}</span>
                            <strong style="text-transform: capitalize; font-size: 13px;">${t.persona}</strong>
                        </div>
                        <code style="font-size: 11px; opacity: 0.6; word-break: break-all;">${t.thread_id}</code>
                    </div>
                `;
            }).join('');

            html += `
                <div class="list-item">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                        <div style="flex: 1;">
                            <div style="font-weight: 600; font-size: 15px; margin-bottom: 4px;">
                                ${session.username || 'Unknown'}
                                ${session.has_subscription ? '<span style="color: #10b981;">💎</span>' : ''}
                            </div>
                            <div style="font-size: 13px; opacity: 0.7; margin-bottom: 8px;">
                                ID: ${session.user_id} | TG: ${session.tg_user_id}
                                ${session.age ? ` | Age: ${session.age}` : ''}
                                ${session.gender ? ` | ${session.gender}` : ''}
                            </div>
                            <div style="font-size: 12px; opacity: 0.6;">
                                Last seen: ${session.last_seen_at ? new Date(session.last_seen_at).toLocaleString() : 'Never'}
                            </div>
                            ${threadsHtml}
                        </div>
                        <button onclick="showUserDetails(${session.user_id})" style="padding: 6px 12px; background: var(--tg-theme-button-color, #3390ec); color: var(--tg-theme-button-text-color, #fff); border: none; border-radius: 6px; font-size: 12px; cursor: pointer; margin-left: 12px;">
                            View User
                        </button>
                    </div>
                </div>
            `;
        });

        sessionsList.innerHTML = html;
    } catch (error) {
        console.error('Error loading sessions:', error);
        document.getElementById('sessionsList').innerHTML = '<div class="error">Error loading sessions</div>';
    }
}

// Initial load with access verification
(async function() {
    const hasAccess = await verifyAccess();
    if (hasAccess) {
        loadDashboard();
        loadUsers();

        // Refresh every 30 seconds
        setInterval(() => {
            loadDashboard();
            const activeTab = document.querySelector('.tab.active').dataset.tab;
            if (activeTab === 'users') {
                loadUsers(currentUserFilter);
            } else if (activeTab === 'subscriptions') {
                loadSubscriptions(currentSubFilter);
            } else if (activeTab === 'events') {
                loadEvents();
            } else if (activeTab === 'tasks') {
                loadTasks();
            } else if (activeTab === 'templates') {
                loadTemplates();
            } else if (activeTab === 'daily-messages') {
                loadDailyMessages();
            } else if (activeTab === 'prompts') {
                loadPrompts(currentPromptFilter);
            } else if (activeTab === 'sessions') {
                loadSessions();
            }
        }, 30000);
    }
})();