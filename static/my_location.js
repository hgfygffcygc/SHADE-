const requestButton = document.querySelector('#get-location');
const clearButton = document.querySelector('#clear-location');
const statusText = document.querySelector('#location-status');
const result = document.querySelector('#location-result');

requestButton.addEventListener('click', () => {
  if (!window.isSecureContext) {
    statusText.textContent = 'Location access requires HTTPS, or localhost during development.';
    return;
  }

  if (!navigator.geolocation) {
    statusText.textContent = 'This browser does not provide location access.';
    return;
  }

  requestButton.disabled = true;
  statusText.textContent = 'Waiting for your browser permission...';
  navigator.geolocation.getCurrentPosition(showLocation, showLocationError, {
    enableHighAccuracy: true,
    timeout: 20000,
    maximumAge: 0,
  });
});

clearButton.addEventListener('click', () => {
  result.replaceChildren();
  const art = document.createElement('div');
  art.className = 'empty-art';
  art.setAttribute('aria-hidden', 'true');
  art.innerHTML = '<span class="orbit orbit-one"></span><span class="orbit orbit-two"></span><span class="orbit-core">?</span>';
  const title = document.createElement('p');
  title.className = 'empty-title';
  title.textContent = 'Details cleared';
  const copy = document.createElement('p');
  copy.className = 'empty-copy';
  copy.textContent = 'Nothing is retained by this page.';
  result.append(art, title, copy);
  statusText.textContent = 'Details removed from this page.';
  clearButton.disabled = true;
});

function showLocation(position) {
  const coordinates = position.coords;
  const values = [
    ['Latitude', coordinates.latitude.toFixed(6)],
    ['Longitude', coordinates.longitude.toFixed(6)],
    ['Accuracy', `${Math.round(coordinates.accuracy)} m`],
    ['Location time', new Date(position.timestamp).toLocaleString()],
    ['Browser', getBrowserName(navigator.userAgent)],
    ['Platform', navigator.userAgentData?.platform || navigator.platform || 'Not provided'],
    ['Device model', navigator.userAgentData?.model || 'Not provided by this browser'],
    ['Screen', `${screen.width} × ${screen.height}`],
    ['Logical CPU cores', navigator.hardwareConcurrency || 'Not provided'],
    ['User agent', navigator.userAgent || 'Not provided'],
  ];

  result.replaceChildren();
  const list = document.createElement('ul');
  list.className = 'result-list location-data-list';
  values.forEach(([label, value]) => {
    const item = document.createElement('li');
    item.className = 'result-item';
    const name = document.createElement('span');
    name.className = 'result-key';
    name.textContent = label;
    const data = document.createElement('span');
    data.className = 'result-value';
    data.textContent = String(value);
    item.append(name, data);
    list.append(item);
  });
  result.append(list);
  statusText.textContent = 'Location received with your browser permission. Details remain in this page.';
  clearButton.disabled = false;
  requestButton.disabled = false;
}

function showLocationError(error) {
  const messages = {
    1: 'Location permission was denied. You can change that in your browser settings.',
    2: 'Your device could not determine a location. Check location services and try again.',
    3: 'The location request timed out. Try again when the device has a clearer signal.',
  };
  statusText.textContent = messages[error.code] || 'The location request failed. Try again.';
  requestButton.disabled = false;
}

function getBrowserName(userAgent) {
  if (/Edg\//.test(userAgent)) return 'Microsoft Edge';
  if (/Firefox\//.test(userAgent)) return 'Mozilla Firefox';
  if (/Chrome\//.test(userAgent) && !/Chromium/.test(userAgent)) return 'Google Chrome';
  if (/Safari\//.test(userAgent) && !/Chrome\//.test(userAgent)) return 'Safari';
  return 'Unknown browser';
}