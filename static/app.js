const modes = {
  domain: {
    label: 'Domain name',
    placeholder: 'example.com',
    hint: 'Enter a domain, with or without https://',
  },
  ip: {
    label: 'IP address',
    placeholder: '8.8.8.8',
    hint: 'Enter an IPv4 or IPv6 address',
  },
  phone: {
    label: 'Phone number',
    placeholder: '+14155552671',
    hint: 'Include the country code, for example +1',
  },
  dns: {
    label: 'Domain name',
    placeholder: 'example.com',
    hint: 'Queries public A, AAAA, MX, NS, TXT, and CAA records',
  },
  rdap: {
    label: 'Domain or public IP address',
    placeholder: 'example.com or 8.8.8.8',
    hint: 'Looks up public registration or network allocation records',
  },
  tls: {
    label: 'HTTPS hostname',
    placeholder: 'example.com',
    hint: 'Inspects the TLS certificate on the hostname’s public HTTPS service',
  },
};

let activeMode = 'domain';
const form = document.querySelector('#lookup-form');
const input = document.querySelector('#lookup-value');
const inputLabel = document.querySelector('#input-label');
const inputHint = document.querySelector('#input-hint');
const button = document.querySelector('#lookup-button');
const resultBody = document.querySelector('#result-body');
const resultCaption = document.querySelector('#result-caption');
const resultActions = document.querySelector('#result-actions');
const copyButton = document.querySelector('#copy-results');
const copyStatus = document.querySelector('#copy-status');
const rememberHistory = document.querySelector('#remember-history');
const historyList = document.querySelector('#history-list');
const clearHistoryButton = document.querySelector('#clear-history');
const historyStorageKey = 'infog.lookup-history.v1';
const historyEnabledKey = 'infog.lookup-history-enabled.v1';
let latestResult = null;
rememberHistory.checked = localStorage.getItem(historyEnabledKey) === 'true';

document.querySelectorAll('.mode-tab').forEach((tab) => {
  tab.addEventListener('click', () => {
    activeMode = tab.dataset.mode;
    document.querySelectorAll('.mode-tab').forEach((item) => {
      const selected = item === tab;
      item.classList.toggle('active', selected);
      item.setAttribute('aria-selected', String(selected));
    });
    inputLabel.textContent = modes[activeMode].label;
    input.placeholder = modes[activeMode].placeholder;
    inputHint.textContent = modes[activeMode].hint;
    input.value = '';
    input.focus();
  });
});

rememberHistory.addEventListener('change', () => {
  if (rememberHistory.checked) {
    localStorage.setItem(historyEnabledKey, 'true');
    renderHistory();
  } else {
    localStorage.removeItem(historyEnabledKey);
    localStorage.removeItem(historyStorageKey);
    renderHistory();
  }
});

clearHistoryButton.addEventListener('click', () => {
  localStorage.removeItem(historyStorageKey);
  renderHistory();
});

copyButton.addEventListener('click', async () => {
  if (!latestResult) return;
  const text = Object.entries(latestResult)
    .map(([key, value]) => `${key}: ${value == null || value === '' ? 'Unavailable' : value}`)
    .join('\n');
  try {
    await navigator.clipboard.writeText(text);
    copyStatus.textContent = 'Copied';
  } catch {
    copyStatus.textContent = 'Clipboard unavailable';
  }
  window.setTimeout(() => { copyStatus.textContent = ''; }, 2200);
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const value = input.value.trim();
  if (!value) return;

  button.disabled = true;
  button.querySelector('span:first-child').textContent = 'Working';
  resultCaption.textContent = 'Contacting lookup service...';
  resultBody.innerHTML = '<p class="loading">Checking the requested information...</p>';

  try {
    const response = await fetch('/api/lookup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: activeMode, value }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'The lookup could not be completed.');
    renderResults(payload.result);
    if (rememberHistory.checked) saveHistory(activeMode, value, payload.result);
  } catch (error) {
    resultCaption.textContent = 'Lookup could not be completed.';
    latestResult = null;
    resultActions.hidden = true;
    resultBody.innerHTML = '';
    const message = document.createElement('p');
    message.className = 'error-message';
    message.textContent = error.message || 'A network error occurred. Please try again.';
    resultBody.append(message);
  } finally {
    button.disabled = false;
    button.querySelector('span:first-child').textContent = 'Look up';
  }
});

function renderResults(result) {
  latestResult = result;
  resultActions.hidden = false;
  resultCaption.textContent = 'Lookup complete.';
  resultBody.innerHTML = '';
  const list = document.createElement('ul');
  list.className = 'result-list';

  Object.entries(result).forEach(([key, value]) => {
    const item = document.createElement('li');
    item.className = 'result-item';
    const label = document.createElement('span');
    label.className = 'result-key';
    label.textContent = key;
    const content = document.createElement('span');
    content.className = 'result-value';
    content.textContent = value == null || value === '' ? 'Unavailable' : String(value);
    item.append(label, content);
    list.append(item);
  });

  resultBody.append(list);
}

function readHistory() {
  try {
    const history = JSON.parse(localStorage.getItem(historyStorageKey) || '[]');
    return Array.isArray(history) ? history : [];
  } catch {
    return [];
  }
}

function saveHistory(mode, value, result) {
  const history = readHistory().filter((item) => !(item.mode === mode && item.value === value));
  history.unshift({ mode, value, result, time: Date.now() });
  localStorage.setItem(historyStorageKey, JSON.stringify(history.slice(0, 8)));
  renderHistory();
}

function renderHistory() {
  historyList.replaceChildren();
  const history = rememberHistory.checked ? readHistory() : [];
  clearHistoryButton.disabled = history.length === 0;
  if (!history.length) {
    const empty = document.createElement('p');
    empty.className = 'history-empty';
    empty.textContent = rememberHistory.checked
      ? 'No recent lookups saved on this device.'
      : 'History is off. Enable it above to remember recent lookups in this browser only.';
    historyList.append(empty);
    return;
  }

  history.forEach((item) => {
    const row = document.createElement('div');
    row.className = 'history-row';
    const details = document.createElement('div');
    details.className = 'history-details';
    const query = document.createElement('strong');
    query.textContent = item.value;
    const kind = document.createElement('span');
    kind.textContent = `${modes[item.mode]?.label || 'Lookup'} · ${new Date(item.time).toLocaleString()}`;
    details.append(query, kind);
    const replay = document.createElement('button');
    replay.className = 'history-replay';
    replay.type = 'button';
    replay.textContent = 'Show';
    replay.setAttribute('aria-label', `Show saved result for ${item.value}`);
    replay.addEventListener('click', () => {
      activeMode = item.mode;
      document.querySelector(`.mode-tab[data-mode="${item.mode}"]`)?.click();
      input.value = item.value;
      renderResults(item.result);
      resultCaption.textContent = `Saved result · ${new Date(item.time).toLocaleString()}`;
    });
    row.append(details, replay);
    historyList.append(row);
  });
}

renderHistory();