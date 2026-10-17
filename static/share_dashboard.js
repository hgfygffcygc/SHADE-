const createButton = document.querySelector('#create-share');
const inviteResult = document.querySelector('#invite-result');
const shareLink = document.querySelector('#share-link');
const copyLinkButton = document.querySelector('#copy-share-link');
const inviteStatus = document.querySelector('#invite-status');
const sharedDetails = document.querySelector('#shared-details');
const closeShareButton = document.querySelector('#close-share');

let ownerToken = null;
let pollTimer = null;

createButton.addEventListener('click', createShare);
copyLinkButton.addEventListener('click', copyShareLink);
closeShareButton.addEventListener('click', closeShare);

async function createShare() {
  createButton.disabled = true;
  inviteStatus.textContent = 'Creating a temporary link...';
  inviteResult.hidden = false;
  try {
    const response = await fetch('/api/location-share', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Could not create the link.');
    ownerToken = payload.owner_token;
    shareLink.value = payload.share_url;
    createButton.hidden = true;
    inviteStatus.textContent = 'Waiting for the recipient to choose whether to share. This session expires in 10 minutes.';
    pollTimer = window.setInterval(checkShare, 2500);
  } catch (error) {
    inviteStatus.textContent = error.message;
    inviteResult.hidden = true;
    createButton.disabled = false;
  }
}

async function copyShareLink() {
  try {
    await navigator.clipboard.writeText(shareLink.value);
    copyLinkButton.textContent = 'Copied';
  } catch {
    shareLink.focus();
    shareLink.select();
    inviteStatus.textContent = 'Copy was blocked; the link is selected so you can copy it manually.';
  }
  window.setTimeout(() => { copyLinkButton.textContent = 'Copy link'; }, 1800);
}

async function checkShare() {
  if (!ownerToken) return;
  try {
    const response = await fetch('/api/location-share/status', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ owner_token: ownerToken }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'This session is no longer available.');
    if (payload.result) {
      window.clearInterval(pollTimer);
      pollTimer = null;
      inviteStatus.textContent = 'The recipient explicitly shared these details. They are temporary and will be deleted when this session closes or expires.';
      renderSharedDetails(payload.result);
    } else if (payload.expires_in <= 0) {
      throw new Error('This link has expired.');
    }
  } catch (error) {
    window.clearInterval(pollTimer);
    pollTimer = null;
    ownerToken = null;
    inviteStatus.textContent = error.message;
    closeShareButton.disabled = true;
    copyLinkButton.disabled = true;
  }
}

function renderSharedDetails(details) {
  sharedDetails.replaceChildren();
  sharedDetails.hidden = false;
  const list = document.createElement('ul');
  list.className = 'result-list location-data-list';
  const fields = [
    ['Latitude', details.latitude],
    ['Longitude', details.longitude],
    ['Accuracy', `${details.accuracy_meters} m`],
    ['Connection IP', details.request_ip],
    ['Shared at', details.shared_at],
    ['Browser', details.browser],
    ['Platform', details.platform],
    ['Device model', details.model],
    ['Screen', details.screen],
    ['Logical CPU cores', details.cpu_cores],
    ['User agent', details.user_agent],
  ];
  fields.forEach(([label, value]) => {
    const item = document.createElement('li');
    item.className = 'result-item';
    const name = document.createElement('span');
    name.className = 'result-key';
    name.textContent = label;
    const data = document.createElement('span');
    data.className = 'result-value';
    data.textContent = String(value ?? 'Not provided');
    item.append(name, data);
    list.append(item);
  });
  sharedDetails.append(list);
}

async function closeShare() {
  if (!ownerToken) return;
  closeShareButton.disabled = true;
  try {
    await fetch('/api/location-share/close', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ owner_token: ownerToken }),
    });
  } finally {
    window.clearInterval(pollTimer);
    pollTimer = null;
    ownerToken = null;
    inviteStatus.textContent = 'Share session deleted.';
    shareLink.value = '';
    sharedDetails.replaceChildren();
    sharedDetails.hidden = true;
    copyLinkButton.disabled = true;
  }
}