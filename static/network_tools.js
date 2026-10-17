const nmapForm = document.querySelector('#nmap-form');
const pcapForm = document.querySelector('#pcap-form');

nmapForm?.addEventListener('submit', async (event) => {
  event.preventDefault();
  const output = document.querySelector('#nmap-result');
  const authorization = document.querySelector('#authorized-scan');
  if (!authorization.checked) {
    showMessage(output, 'Confirm authorization before running a check.', true);
    return;
  }

  const button = nmapForm.querySelector('button[type="submit"]');
  button.disabled = true;
  showMessage(output, 'Running the bounded TCP check...');
  try {
    const response = await fetch('/api/network/nmap', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target: document.querySelector('#nmap-target').value.trim(),
        start_port: Number(document.querySelector('#port-start').value),
        end_port: Number(document.querySelector('#port-end').value),
        authorized: true,
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'The host check failed.');
    renderRows(output, [
      ['Target', payload.result.target],
      ['Open TCP ports', payload.result.ports.length ? payload.result.ports.map((port) => `${port.port} (${port.service})`).join(', ') : 'None found in selected range'],
      ['Scope', payload.result.note],
    ]);
  } catch (error) {
    showMessage(output, error.message, true);
  } finally {
    button.disabled = false;
  }
});

pcapForm?.addEventListener('submit', async (event) => {
  event.preventDefault();
  const output = document.querySelector('#pcap-result');
  const authorization = document.querySelector('#authorized-capture');
  const file = document.querySelector('#pcap-file').files[0];
  if (!authorization.checked) {
    showMessage(output, 'Confirm authorization before analyzing this capture.', true);
    return;
  }
  if (!file || file.size > 5 * 1024 * 1024) {
    showMessage(output, 'Choose a capture file no larger than 5 MB.', true);
    return;
  }

  const button = pcapForm.querySelector('button[type="submit"]');
  button.disabled = true;
  showMessage(output, 'Analyzing the existing capture offline...');
  const data = new FormData();
  data.append('capture', file);
  try {
    const response = await fetch('/api/network/pcap', { method: 'POST', body: data });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Capture analysis failed.');
    renderRows(output, [
      ['File', payload.result.filename],
      ['Packets analyzed', `${payload.result.packets_analyzed} (limit ${payload.result.packet_limit})`],
      ['Protocols', payload.result.protocols.map((item) => `${item.name}: ${item.packets}`).join(', ') || 'None decoded'],
      ['Endpoints', payload.result.endpoints.map((item) => `${item.address}: ${item.packets}`).join(', ') || 'None decoded'],
      ['Handling', payload.result.note],
    ]);
  } catch (error) {
    showMessage(output, error.message, true);
  } finally {
    button.disabled = false;
  }
});

function showMessage(container, text, isError = false) {
  container.replaceChildren();
  const message = document.createElement('p');
  message.className = isError ? 'error-message' : 'diagnostic-status';
  message.textContent = text;
  container.append(message);
}

function renderRows(container, rows) {
  container.replaceChildren();
  const list = document.createElement('ul');
  list.className = 'result-list';
  rows.forEach(([label, value]) => {
    const item = document.createElement('li');
    item.className = 'result-item';
    const key = document.createElement('span');
    key.className = 'result-key';
    key.textContent = label;
    const content = document.createElement('span');
    content.className = 'result-value';
    content.textContent = value;
    item.append(key, content);
    list.append(item);
  });
  container.append(list);
}