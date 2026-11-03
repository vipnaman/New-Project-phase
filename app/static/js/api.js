async function fetchJson(url, options = {}) {
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}),
      ...(options.headers || {})
    },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.message || 'Request failed');
  }
  return data;
}

function updateRequestCardStatus(card, status) {
  const details = card.querySelector('[data-request-details]');
  if (details) {
    const parts = details.textContent.split(' · ');
    if (['OPEN', 'FULFILLED', 'CANCELLED', 'EXPIRED'].includes(parts[parts.length - 1])) parts.pop();
    parts.push(status);
    details.textContent = parts.join(' · ');
  }
  card.querySelectorAll('[data-cancel-request], [data-fulfill-request]').forEach(button => button.remove());
}

function renderDonorCards(items) {
  const container = document.getElementById('donorResults');
  if (!container) return;
  container.replaceChildren();
  if (!items?.length) {
    const empty = document.createElement('div');
    empty.className = 'info-card';
    const title = document.createElement('h3');
    title.textContent = 'No matching verified donors found.';
    const message = document.createElement('p');
    message.textContent = 'Try another location or check back later.';
    empty.append(title, message);
    container.appendChild(empty);
    return;
  }
  items.forEach((item) => {
    const card = document.createElement('article');
    card.className = 'donor-card';
    const title = document.createElement('h3');
    title.textContent = item.name || 'Verified donor';
    const meta = document.createElement('p');
    meta.className = 'meta';
    meta.textContent = [item.blood_group, item.city, item.state].filter(Boolean).join(' · ');
    const verification = document.createElement('p');
    verification.className = 'meta';
    verification.textContent = item.emergency_available ? 'Verified · Emergency available' : 'Verified · Available';
    const button = document.createElement('button');
    button.className = 'btn btn-primary';
    button.type = 'button';
    button.dataset.contactDonor = item.id;
    button.textContent = 'Request contact';
    const reportButton = document.createElement('button');
    reportButton.className = 'btn btn-ghost';
    reportButton.type = 'button';
    reportButton.dataset.reportListingType = 'donor';
    reportButton.dataset.reportListingId = item.id;
    reportButton.textContent = 'Report listing';
    card.append(title, meta, verification, button, reportButton);
    container.appendChild(card);
  });
}

function bindSearchForm() {
  const form = document.getElementById('homeSearchForm');
  if (form) {
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const formData = new FormData(form);
      const params = new URLSearchParams();
      for (const [key, value] of formData.entries()) {
        if (value) params.append(key, value);
      }
      window.location.href = `/find-blood?${params.toString()}`;
    });
  }

  const donorSearchForm = document.getElementById('donorSearchForm');
  if (donorSearchForm) {
    donorSearchForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const formData = new FormData(donorSearchForm);
      const params = new URLSearchParams();
      for (const [key, value] of formData.entries()) {
        if (value) params.append(key, value);
      }
      const data = await fetchJson(`/api/donors?${params.toString()}`);
      renderDonorCards(data.data.items || []);
    });
  }

  const registerForm = document.getElementById('registerForm');
  if (registerForm) {
    registerForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const payload = Object.fromEntries(new FormData(registerForm).entries());
      const result = await fetchJson('/api/auth/register', { method: 'POST', body: JSON.stringify(payload) });
      if (result.success) {
        window.location.href = '/login';
      }
    });
  }

  const loginForm = document.getElementById('loginForm');
  if (loginForm) {
    loginForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const payload = Object.fromEntries(new FormData(loginForm).entries());
      payload.remember = loginForm.elements.namedItem('remember').checked;
      const message = document.getElementById('loginMessage');
      const submit = loginForm.querySelector('[type="submit"]');
      submit.disabled = true;
      if (message) message.textContent = '';
      try {
        const result = await fetchJson('/api/auth/login', { method: 'POST', body: JSON.stringify(payload) });
        if (result.success) {
          window.location.href = result.data.user.role === 'ADMIN' ? '/admin' : '/dashboard';
        }
      } catch (error) {
        if (message) message.textContent = error.message;
      } finally {
        submit.disabled = false;
      }
    });
  }

  const notificationPreferencesForm = document.getElementById('notificationPreferencesForm');
  if (notificationPreferencesForm) {
    const enabled = notificationPreferencesForm.elements.namedItem('email_notifications_enabled');
    const status = document.getElementById('notificationPreferencesStatus');
    fetchJson('/api/notifications/preferences')
      .then(({ data }) => { enabled.checked = data.email_notifications_enabled; })
      .catch((error) => { if (status) status.textContent = error.message; });
    notificationPreferencesForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const submit = notificationPreferencesForm.querySelector('[type="submit"]');
      submit.disabled = true;
      try {
        await fetchJson('/api/notifications/preferences', {
          method: 'PATCH',
          body: JSON.stringify({ email_notifications_enabled: enabled.checked })
        });
        if (status) status.textContent = 'Notification preferences saved.';
      } catch (error) {
        if (status) status.textContent = error.message;
      } finally {
        submit.disabled = false;
      }
    });
  }

  const deleteAccountForm = document.getElementById('deleteAccountForm');
  if (deleteAccountForm) {
    deleteAccountForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (!window.confirm('Remove your account? This action cannot be undone.')) return;
      const status = document.getElementById('deleteAccountStatus');
      const submit = deleteAccountForm.querySelector('[type="submit"]');
      submit.disabled = true;
      try {
        const password = new FormData(deleteAccountForm).get('password');
        await fetchJson('/api/auth/me', { method: 'DELETE', body: JSON.stringify({ password }) });
        window.location.href = '/';
      } catch (error) {
        if (status) status.textContent = error.message;
      } finally {
        submit.disabled = false;
      }
    });
  }

  const appearanceForm = document.getElementById('appearanceSettingsForm');
  if (appearanceForm) {
    const status = document.getElementById('appearanceSettingsStatus');
    const palette = appearanceForm.elements.namedItem('palette');
    const motionLevel = appearanceForm.elements.namedItem('motion_level');
    const background = appearanceForm.elements.namedItem('live_background');
    fetchJson('/api/admin/appearance')
      .then(({ data }) => {
        palette.value = data.palette;
        motionLevel.value = data.motion_level;
        background.checked = data.live_background;
      })
      .catch((error) => { if (status) status.textContent = error.message; });
    appearanceForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const submit = appearanceForm.querySelector('[type="submit"]');
      submit.disabled = true;
      try {
        await fetchJson('/api/admin/appearance', {
          method: 'PATCH',
          body: JSON.stringify({ palette: palette.value, motion_level: motionLevel.value, live_background: background.checked })
        });
        if (status) status.textContent = 'Appearance saved. Changes are active across the site.';
      } catch (error) {
        if (status) status.textContent = error.message;
      } finally {
        submit.disabled = false;
      }
    });
  }

  const hospitalForm = document.getElementById('adminHospitalForm');
  if (hospitalForm) {
    hospitalForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const status = document.getElementById('hospitalCreateStatus');
      const submit = hospitalForm.querySelector('[type="submit"]');
      submit.disabled = true;
      try {
        const payload = Object.fromEntries(new FormData(hospitalForm).entries());
        await fetchJson('/api/admin/hospitals', { method: 'POST', body: JSON.stringify(payload) });
        hospitalForm.reset();
        if (status) status.textContent = 'Hospital added as unverified. Review its details before verification.';
        await loadAdminTable(adminTableConfigs.find(config => config.key === 'hospitals'));
      } catch (error) {
        if (status) status.textContent = error.message;
      } finally {
        submit.disabled = false;
      }
    });
  }

  const donorForm = document.getElementById('donorRegistrationForm');
  if (donorForm) {
    donorForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const payload = Object.fromEntries(new FormData(donorForm).entries());
      const status = document.getElementById('donorFormStatus');
      const submit = donorForm.querySelector('[type="submit"]');
      submit.disabled = true;
      if (status) status.textContent = '';
      try {
        await fetchJson('/api/donors', { method: 'POST', body: JSON.stringify(payload) });
        if (status) status.textContent = 'Donor profile saved. It will be listed after account verification.';
        window.setTimeout(() => { window.location.href = '/dashboard'; }, 800);
      } catch (error) {
        if (status) status.textContent = error.message;
      } finally {
        submit.disabled = false;
      }
    });
  }

  const requestForm = document.getElementById('bloodRequestForm');
  if (requestForm) {
    requestForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const payload = Object.fromEntries(new FormData(requestForm).entries());
      const status = document.getElementById('requestFormStatus');
      const submit = requestForm.querySelector('[type="submit"]');
      submit.disabled = true;
      if (status) status.textContent = '';
      try {
        const result = await fetchJson('/api/requests', { method: 'POST', body: JSON.stringify(payload) });
        if (status) status.textContent = `Request published. ${result.data.matches} compatible donor match(es) notified.`;
        window.setTimeout(() => { window.location.href = '/blood-requests'; }, 900);
      } catch (error) {
        if (status) status.textContent = error.message;
      } finally {
        submit.disabled = false;
      }
    });
  }
}

function createAdminCell(row, value) {
  const cell = document.createElement('td');
  cell.textContent = value == null || value === '' ? '—' : String(value);
  row.appendChild(cell);
}

async function loadAdminTable(config) {
  const tableBody = document.getElementById(config.bodyId);
  if (!tableBody) return;
  const result = await fetchJson(config.endpoint);
  const items = result.data.items || [];
  tableBody.replaceChildren();
  if (!items.length) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = config.columns.length + 2;
    cell.textContent = 'No records yet.';
    row.appendChild(cell);
    tableBody.appendChild(row);
    return;
  }

  items.forEach((item) => {
    const row = document.createElement('tr');
    row.dataset.adminRow = config.key;
    row.dataset.recordId = item.id;
    config.columns.forEach((column) => {
      if (column.field) {
        const cell = document.createElement('td');
        const input = document.createElement('input');
        input.type = column.type || 'text';
        input.value = column.value(item) || '';
        input.setAttribute('aria-label', `${column.label} for ${item.name}`);
        input.dataset.adminField = column.field;
        input.className = 'admin-inline-editor';
        cell.appendChild(input);
        row.appendChild(cell);
      } else {
        createAdminCell(row, column.value(item));
      }
    });

    const controlCell = document.createElement('td');
    const select = document.createElement('select');
    select.setAttribute('aria-label', `${config.label} for ${item.name || item.patient_name || item.hospital_name || item.target || 'record'}`);
    const currentValue = config.current(item);
    config.options.forEach(([label, value]) => {
      const option = new Option(label, value, false, String(value) === String(currentValue));
      select.add(option);
    });
    controlCell.appendChild(select);
    row.appendChild(controlCell);

    const actionCell = document.createElement('td');
    const saveButton = document.createElement('button');
    saveButton.type = 'button';
    saveButton.className = 'btn btn-ghost admin-save';
    saveButton.dataset.adminSave = config.key;
    saveButton.textContent = 'Save';
    actionCell.appendChild(saveButton);
    if (config.key === 'users') {
      const reviewButton = document.createElement('button');
      reviewButton.type = 'button';
      reviewButton.className = 'btn btn-ghost admin-review';
      reviewButton.dataset.userReview = item.id;
      reviewButton.dataset.verified = String(item.is_verified);
      reviewButton.textContent = item.is_verified ? 'Unreview' : 'Mark reviewed';
      actionCell.appendChild(reviewButton);
    }
    row.appendChild(actionCell);
    tableBody.appendChild(row);
  });
}

const adminTableConfigs = [
  { key: 'users', bodyId: 'adminUsersTable', endpoint: '/api/admin/users', label: 'Account access', columns: [
    { value: item => item.name }, { value: item => item.email }, { value: item => item.role }, { value: item => new Date(item.created_at).toLocaleDateString() }, { value: item => item.is_verified ? 'Reviewed' : 'Pending review' }
  ], current: item => item.is_active, options: [['Active', true], ['Suspended', false]] },
  { key: 'donors', bodyId: 'adminDonorsTable', endpoint: '/api/admin/donors', label: 'Availability', columns: [
    { value: item => item.name },
    { field: 'blood_group', label: 'Blood group', value: item => item.blood_group },
    { field: 'city', label: 'City', value: item => item.city },
    { field: 'state', label: 'State', value: item => item.state },
    { value: item => item.emergency_available ? 'Emergency ready' : 'Standard' }
  ], current: item => item.visibility === 'private' ? 'hidden' : item.availability, options: [['Available', 'available'], ['Busy', 'busy'], ['Hidden', 'hidden']] },
  { key: 'requests', bodyId: 'adminRequestsTable', endpoint: '/api/admin/requests', label: 'Request status', columns: [
    { value: item => item.patient_name }, { value: item => item.blood_group }, { value: item => item.units_required }, { value: item => item.urgency }, { value: item => [item.city, item.state].filter(Boolean).join(', ') }
  ], current: item => item.status, options: [['Open', 'OPEN'], ['Fulfilled', 'FULFILLED'], ['Cancelled', 'CANCELLED']] },
  { key: 'hospitals', bodyId: 'adminHospitalsTable', endpoint: '/api/admin/hospitals', label: 'Verification', columns: [
    { field: 'name', label: 'Hospital name', value: item => item.name },
    { field: 'city', label: 'City', value: item => item.city },
    { field: 'state', label: 'State', value: item => item.state },
    { field: 'address', label: 'Address', value: item => item.address },
    { field: 'phone', label: 'Phone', value: item => item.phone },
    { field: 'email', label: 'Email', type: 'email', value: item => item.email }
  ], current: item => item.verified, options: [['Verified', true], ['Unverified', false]] },
  { key: 'reports', bodyId: 'adminReportsTable', endpoint: '/api/admin/listing-reports', label: 'Report status', columns: [
    { value: item => item.target_type }, { value: item => item.target }, { value: item => item.reason }, { value: item => item.reporter }, { value: item => new Date(item.created_at).toLocaleString() }
  ], current: item => item.status, options: [['Open', 'OPEN'], ['Resolved', 'RESOLVED'], ['Dismissed', 'DISMISSED']] }
];

async function saveAdminRecord(button) {
  const config = adminTableConfigs.find(item => item.key === button.dataset.adminSave);
  const row = button.closest('tr');
  const value = row.querySelector('select').value;
  const numericId = row.dataset.recordId;
  const endpointMap = {
    users: `/api/admin/users/${numericId}`,
    donors: `/api/admin/donors/${numericId}`,
    requests: `/api/admin/requests/${numericId}`,
    hospitals: `/api/admin/hospitals/${numericId}`,
    reports: `/api/admin/listing-reports/${numericId}`
  };
  const payloadMap = {
    users: { is_active: value === 'true' },
    donors: {
      availability: value === 'hidden' ? 'busy' : value,
      visibility: value === 'hidden' ? 'private' : 'public',
      ...Object.fromEntries([...row.querySelectorAll('[data-admin-field]')].map(input => [input.dataset.adminField, input.value]))
    },
    requests: { status: value },
    hospitals: { verified: value === 'true', ...Object.fromEntries([...row.querySelectorAll('[data-admin-field]')].map(input => [input.dataset.adminField, input.value])) },
    reports: { status: value }
  };
  const status = document.getElementById('adminStatus');
  button.disabled = true;
  try {
    await fetchJson(endpointMap[config.key], { method: 'PATCH', body: JSON.stringify(payloadMap[config.key]) });
    button.textContent = 'Saved';
    if (status) status.textContent = `${config.label} updated.`;
  } catch (error) {
    if (status) status.textContent = error.message;
    button.textContent = 'Retry';
  } finally {
    button.disabled = false;
  }
}

async function reviewUser(button) {
  button.disabled = true;
  const nextValue = button.dataset.verified !== 'true';
  const status = document.getElementById('adminStatus');
  try {
    await fetchJson(`/api/admin/users/${button.dataset.userReview}`, {
      method: 'PATCH',
      body: JSON.stringify({ is_verified: nextValue })
    });
    button.dataset.verified = String(nextValue);
    button.textContent = nextValue ? 'Unreview' : 'Mark reviewed';
    button.closest('tr').cells[4].textContent = nextValue ? 'Reviewed' : 'Pending review';
    if (status) status.textContent = 'Account review status updated.';
  } catch (error) {
    if (status) status.textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

function renderNotifications(items) {
  const container = document.getElementById('notificationList');
  if (!container) return;
  container.replaceChildren();
  if (!items.length) {
    const empty = document.createElement('p');
    empty.textContent = 'No notifications yet.';
    container.appendChild(empty);
    return;
  }
  items.forEach((item) => {
    const card = document.createElement('article');
    card.className = 'notification-item';
    const title = document.createElement('strong');
    title.textContent = item.title;
    const message = document.createElement('p');
    message.textContent = item.message;
    const time = document.createElement('small');
    time.textContent = new Date(item.created_at).toLocaleString();
    const delivery = document.createElement('small');
    delivery.textContent = `Email: ${String(item.email_delivery_status || 'NOT_REQUESTED').toLowerCase().replaceAll('_', ' ')}`;
    card.append(title, message, time, delivery);
    if (!item.is_read) {
      const button = document.createElement('button');
      button.className = 'btn btn-ghost';
      button.type = 'button';
      button.dataset.markNotificationRead = item.id;
      button.textContent = 'Mark as read';
      card.appendChild(button);
    }
    container.appendChild(card);
  });
}

function renderContactRequests(items) {
  const container = document.getElementById('contactRequestList');
  if (!container) return;
  container.replaceChildren();
  if (!items.length) {
    const empty = document.createElement('p');
    empty.textContent = 'No contact requests yet.';
    container.appendChild(empty);
    return;
  }
  items.forEach((item) => {
    const card = document.createElement('article');
    card.className = 'notification-item';
    const title = document.createElement('strong');
    title.textContent = item.can_respond ? `${item.initiator_name} would like to contact you` : `Contact request with ${item.initiator_name}`;
    const detail = document.createElement('p');
    detail.textContent = [item.blood_group, item.city, item.status.toLowerCase()].filter(Boolean).join(' · ');
    card.append(title, detail);
    if (item.status === 'ACCEPTED' && item.contact_phone) {
      const phone = document.createElement('p');
      phone.textContent = `Phone: ${item.contact_phone}`;
      card.appendChild(phone);
    }
    if (item.can_respond) {
      ['ACCEPTED', 'DECLINED'].forEach((decision) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = decision === 'ACCEPTED' ? 'btn btn-primary' : 'btn btn-ghost';
        button.dataset.contactResponse = item.id;
        button.dataset.decision = decision;
        button.textContent = decision === 'ACCEPTED' ? 'Accept' : 'Decline';
        card.appendChild(button);
      });
    }
    container.appendChild(card);
  });
}

async function loadNotificationCenter() {
  const status = document.getElementById('notificationStatus');
  try {
    const [notifications, contacts] = await Promise.all([
      fetchJson('/api/notifications'),
      fetchJson('/api/contact-requests')
    ]);
    renderNotifications(notifications.data || []);
    renderContactRequests(contacts.data.items || []);
  } catch (error) {
    if (status) status.textContent = error.message;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  bindSearchForm();

  const hospitalSelect = document.querySelector('[data-hospital-select]');
  if (hospitalSelect) {
    fetchJson('/api/hospitals')
      .then(({ data }) => {
        (data.items || []).forEach((hospital) => {
          const location = [hospital.city, hospital.state].filter(Boolean).join(', ');
          hospitalSelect.add(new Option(location ? `${hospital.name} · ${location}` : hospital.name, hospital.id));
        });
      })
      .catch(() => {
        hospitalSelect.add(new Option('Verified hospital list unavailable', ''));
      });
    const reportButton = document.getElementById('reportSelectedHospital');
    if (reportButton) {
      const updateVisibility = () => { reportButton.hidden = !hospitalSelect.value; };
      hospitalSelect.addEventListener('change', updateVisibility);
      updateVisibility();
    }
  }

  const queryParams = new URLSearchParams(window.location.search);
  const donorSearchForm = document.getElementById('donorSearchForm');
  if (donorSearchForm) {
    for (const [key, value] of queryParams.entries()) {
      const field = donorSearchForm.elements.namedItem(key);
      if (field) field.value = value;
    }
    if (queryParams.toString()) {
      fetchJson(`/api/donors?${queryParams.toString()}`)
        .then(result => renderDonorCards(result.data.items || []))
        .catch(() => renderDonorCards([]));
    }
  }

  const requestList = document.getElementById('requestList');
  if (requestList) {
    fetchJson('/api/requests')
      .then(result => {
        const items = result.data.items || [];
        requestList.replaceChildren();
        if (!items.length) {
          const empty = document.createElement('div');
          empty.className = 'info-card';
          const heading = document.createElement('h3');
          heading.textContent = 'No active blood requests.';
          const note = document.createElement('p');
          note.textContent = 'Check back soon or submit a request.';
          empty.append(heading, note);
          requestList.appendChild(empty);
          return;
        }
        items.forEach((item) => {
          const card = document.createElement('article');
          card.className = 'request-card';
          const header = document.createElement('div');
          header.className = 'request-header';
          const urgency = document.createElement('span');
          urgency.className = `badge ${item.urgency === 'emergency' ? 'danger' : 'warning'}`;
          urgency.textContent = item.urgency;
          const group = document.createElement('span');
          group.textContent = item.blood_group;
          header.append(urgency, group);
          const heading = document.createElement('h3');
          heading.textContent = item.hospital || 'Blood request';
          const location = document.createElement('p');
          location.textContent = [item.city, item.state].filter(Boolean).join(', ');
          const units = document.createElement('p');
          units.textContent = `${item.units_required} unit(s) required`;
          units.dataset.requestDetails = '';
          card.append(header, heading, location, units);
          if (item.status === 'OPEN') {
            const interestButton = document.createElement('button');
            interestButton.type = 'button';
            interestButton.className = 'btn btn-secondary';
            interestButton.dataset.requestInterest = item.id;
            interestButton.textContent = 'I can help';
            card.appendChild(interestButton);
          }
          if (item.is_owner && item.status === 'OPEN') {
            const cancelButton = document.createElement('button');
            cancelButton.type = 'button';
            cancelButton.className = 'btn btn-ghost';
            cancelButton.dataset.cancelRequest = item.id;
            cancelButton.textContent = 'Cancel request';
            const fulfillButton = document.createElement('button');
            fulfillButton.type = 'button';
            fulfillButton.className = 'btn btn-secondary';
            fulfillButton.dataset.fulfillRequest = item.id;
            fulfillButton.textContent = 'Mark fulfilled';
            card.append(cancelButton, fulfillButton);
          }
          requestList.appendChild(card);
        });
      })
      .catch(() => {
        requestList.textContent = 'Unable to load requests.';
      });
  }

  const dashboardRequests = document.getElementById('dashboardRequests');
  if (dashboardRequests) {
    Promise.all([fetchJson('/api/dashboard/summary'), fetchJson('/api/requests?status=ALL')])
      .then(([summary, requests]) => {
        document.getElementById('dashboardDonorStatus').textContent = summary.data.donor_status;
        document.getElementById('dashboardOpenRequests').textContent = summary.data.open_requests;
        document.getElementById('dashboardUnreadNotifications').textContent = summary.data.unread_notifications;
        document.getElementById('dashboardDonations').textContent = summary.data.donations;
        dashboardRequests.replaceChildren();
        const items = requests.data.items || [];
        if (!items.length) {
          const empty = document.createElement('p');
          empty.textContent = 'You have not created any blood requests yet.';
          dashboardRequests.appendChild(empty);
          return;
        }
        items.forEach((item) => {
          const card = document.createElement('article');
          card.className = 'request-card';
          const title = document.createElement('h3');
          title.textContent = item.patient_name || 'Your blood request';
          const details = document.createElement('p');
          details.textContent = `${item.blood_group} · ${item.units_required} unit(s) · ${item.status}`;
          details.dataset.requestDetails = '';
          const location = document.createElement('p');
          location.textContent = [item.city, item.state].filter(Boolean).join(', ');
          card.append(title, details, location);
          if (item.status === 'OPEN') {
            const cancel = document.createElement('button');
            cancel.type = 'button';
            cancel.className = 'btn btn-ghost';
            cancel.dataset.cancelRequest = item.id;
            cancel.textContent = 'Cancel request';
            const fulfill = document.createElement('button');
            fulfill.type = 'button';
            fulfill.className = 'btn btn-secondary';
            fulfill.dataset.fulfillRequest = item.id;
            fulfill.textContent = 'Mark fulfilled';
            card.append(cancel, fulfill);
          }
          dashboardRequests.appendChild(card);
        });
      })
      .catch((error) => {
        const status = document.getElementById('dashboardStatus');
        if (status) status.textContent = error.message;
      });
  }

  const adminStats = document.getElementById('adminUsersCount');
  if (adminStats) {
    fetchJson('/api/admin/stats')
      .then(result => {
        const stats = result.data;
        document.getElementById('adminUsersCount').textContent = stats.users || 0;
        document.getElementById('adminDonorsCount').textContent = stats.donors || 0;
        document.getElementById('adminOpenRequestsCount').textContent = stats.open_requests || 0;
        document.getElementById('adminHospitalsCount').textContent = stats.hospitals || 0;
      })
      .catch(() => {});
  }

  if (adminTableConfigs.some(config => document.getElementById(config.bodyId))) {
    Promise.all(adminTableConfigs.filter(config => document.getElementById(config.bodyId)).map((config) => loadAdminTable(config).catch(() => {
      const status = document.getElementById('adminStatus');
      if (status) status.textContent = 'Unable to load one or more admin lists.';
    })));
    document.addEventListener('click', (event) => {
      const button = event.target.closest('[data-admin-save]');
      if (button) saveAdminRecord(button);
      const reviewButton = event.target.closest('[data-user-review]');
      if (reviewButton) reviewUser(reviewButton);
    });
  }

  document.querySelectorAll('[data-table-filter]').forEach((filter) => {
    filter.addEventListener('input', () => {
      const body = document.getElementById(filter.dataset.tableFilter);
      const term = filter.value.trim().toLocaleLowerCase();
      body?.querySelectorAll('tr').forEach((row) => {
        row.hidden = !row.textContent.toLocaleLowerCase().includes(term);
      });
    });
  });

  const activityTable = document.getElementById('adminActivitiesTable');
  if (activityTable) {
    fetchJson('/api/admin/activities')
      .then(({ data }) => {
        activityTable.replaceChildren();
        (data.items || []).forEach((activity) => {
          const row = document.createElement('tr');
          [activity.action, activity.target_type, activity.target_id, activity.metadata, activity.created_at]
            .forEach(value => createAdminCell(row, value));
          activityTable.appendChild(row);
        });
        if (!data.items?.length) {
          const row = document.createElement('tr');
          createAdminCell(row, 'No recorded admin actions yet.');
          activityTable.appendChild(row);
        }
      })
      .catch((error) => {
        const status = document.getElementById('adminStatus');
        if (status) status.textContent = error.message;
      });
  }

  if (document.getElementById('notificationList')) loadNotificationCenter();

  document.addEventListener('click', async (event) => {
    const contactButton = event.target.closest('[data-contact-donor]');
    const responseButton = event.target.closest('[data-contact-response]');
    const readButton = event.target.closest('[data-mark-notification-read]');
    const interestButton = event.target.closest('[data-request-interest]');
    const cancelButton = event.target.closest('[data-cancel-request]');
    const fulfillButton = event.target.closest('[data-fulfill-request]');
    const reportButton = event.target.closest('[data-report-listing-type]');
    const hospitalReportButton = event.target.closest('#reportSelectedHospital');
    const status = document.getElementById('donorSearchStatus') || document.getElementById('notificationStatus') || document.getElementById('requestStatus') || document.getElementById('dashboardStatus');
    if (reportButton) {
      const reason = window.prompt('What is incorrect or unsafe about this listing?');
      if (reason === null) return;
      reportButton.disabled = true;
      try {
        await fetchJson('/api/listing-reports', {
          method: 'POST',
          body: JSON.stringify({
            target_type: reportButton.dataset.reportListingType,
            target_id: reportButton.dataset.reportListingId,
            reason
          })
        });
        const message = document.getElementById('donorSearchStatus');
        if (message) message.textContent = 'Report sent for administrator review.';
      } catch (error) {
        const message = document.getElementById('donorSearchStatus');
        if (message) message.textContent = error.message;
        reportButton.disabled = false;
      }
    }
    if (hospitalReportButton) {
      const hospitalSelect = document.querySelector('[data-hospital-select]');
      const reason = window.prompt('What is incorrect or unsafe about this hospital listing?');
      if (reason === null) return;
      hospitalReportButton.disabled = true;
      try {
        await fetchJson('/api/listing-reports', {
          method: 'POST',
          body: JSON.stringify({ target_type: 'hospital', target_id: hospitalSelect.value, reason })
        });
        document.getElementById('hospitalReportStatus').textContent = 'Report sent for administrator review.';
      } catch (error) {
        document.getElementById('hospitalReportStatus').textContent = error.message;
      } finally {
        hospitalReportButton.disabled = false;
      }
    }
    if (contactButton) {
      contactButton.disabled = true;
      try {
        await fetchJson('/api/contact-requests', {
          method: 'POST',
          body: JSON.stringify({ donor_profile_id: contactButton.dataset.contactDonor })
        });
        contactButton.textContent = 'Request sent';
        if (status) status.textContent = 'Contact request sent. Your phone stays private until accepted.';
      } catch (error) {
        contactButton.disabled = false;
        if (status) status.textContent = error.message;
      }
    }
    if (responseButton) {
      responseButton.disabled = true;
      try {
        await fetchJson(`/api/contact-requests/${responseButton.dataset.contactResponse}/respond`, {
          method: 'POST',
          body: JSON.stringify({ status: responseButton.dataset.decision })
        });
        await loadNotificationCenter();
      } catch (error) {
        responseButton.disabled = false;
        if (status) status.textContent = error.message;
      }
    }
    if (readButton) {
      readButton.disabled = true;
      try {
        await fetchJson(`/api/notifications/${readButton.dataset.markNotificationRead}/read`, { method: 'POST' });
        await loadNotificationCenter();
      } catch (error) {
        readButton.disabled = false;
        if (status) status.textContent = error.message;
      }
    }
    if (interestButton) {
      interestButton.disabled = true;
      try {
        await fetchJson(`/api/requests/${interestButton.dataset.requestInterest}/interest`, { method: 'POST' });
        interestButton.textContent = 'Interest sent';
        if (status) status.textContent = 'Your interest is sent. Your phone remains private until the requester accepts.';
      } catch (error) {
        interestButton.disabled = false;
        if (status) status.textContent = error.message;
      }
    }
    if (cancelButton) {
      cancelButton.disabled = true;
      try {
        await fetchJson(`/api/requests/${cancelButton.dataset.cancelRequest}`, {
          method: 'PATCH',
          body: JSON.stringify({ status: 'CANCELLED' })
        });
        const card = cancelButton.closest('.request-card');
        updateRequestCardStatus(card, 'CANCELLED');
        if (status) status.textContent = 'Your request was cancelled.';
      } catch (error) {
        cancelButton.disabled = false;
        if (status) status.textContent = error.message;
      }
    }
    if (fulfillButton) {
      fulfillButton.disabled = true;
      try {
        await fetchJson(`/api/requests/${fulfillButton.dataset.fulfillRequest}`, {
          method: 'PATCH',
          body: JSON.stringify({ status: 'FULFILLED' })
        });
        const card = fulfillButton.closest('.request-card');
        updateRequestCardStatus(card, 'FULFILLED');
        if (status) status.textContent = 'Your request was marked fulfilled.';
      } catch (error) {
        fulfillButton.disabled = false;
        if (status) status.textContent = error.message;
      }
    }
  });

  const analyticsCount = document.getElementById('adminFulfilledCount');
  if (analyticsCount) {
    fetchJson('/api/admin/stats').then(({ data }) => {
      analyticsCount.textContent = data.fulfilled_requests || 0;
      document.getElementById('adminOpenRequestsCount').textContent = data.open_requests || 0;
      document.getElementById('adminDonorsCount').textContent = data.donors || 0;
      document.getElementById('adminHospitalsCount').textContent = data.hospitals || 0;
    });
  }
});
