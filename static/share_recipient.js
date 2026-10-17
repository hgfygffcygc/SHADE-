const submitButton = document.querySelector('#submit-share');
const statusMessage = document.querySelector('#recipient-status');
const resultPanel = document.querySelector('#recipient-result');
const shareToken = new URLSearchParams(window.location.hash.slice(1)).get('token');
if (window.location.hash) {
  window.history.replaceState(null, '', window.location.pathname);
}

submitButton.disabled = !shareToken;
if (!shareToken) {
  statusMessage.textContent = 'This link is incomplete or invalid. Ask the sender for a fresh link.';
}

submitButton.addEventListener('click', () => {
  if (!shareToken) return;
  if (!window.isSecureContext) {
    statusMessage.textContent = 'Location sharing requires HTTPS, or localhost during development.';
    return;
  }
  if (!navigator.geolocation) {
    statusMessage.textContent = 'This browser does not provide location access. Nothing was shared.';
    return;
  }

  submitButton.disabled = true;
  statusMessage.textContent = 'Your browser will now ask whether to allow location access.';
  navigator.geolocation.getCurrentPosition(shareLocation, locationError, {
    enableHighAccuracy: true,
    timeout: 20000,
    maximumAge: 0,
  });
});

async function shareLocation(position) {
  statusMessage.textContent = 'Sending the details you agreed to share...';
  const coords = position.coords;
  const payload = {
    share_token: shareToken,
    consent: true,
    coordinates: {
      latitude: coords.latitude,
      longitude: coords.longitude,
      accuracy: coords.accuracy,
    },
    device: {
      browser: browserName(navigator.userAgent),
      platform: navigator.userAgentData?.platform || navigator.platform || '',
      model: navigator.userAgentData?.model || '',
      screen: `${screen.width} x ${screen.height}`,
      cpu_cores: navigator.hardwareConcurrency ? String(navigator.hardwareConcurrency) : '',
      user_agent: navigator.userAgent || '',
    },
  };

  try {
    const response = await fetch('/api/location-share/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'The details could not be shared.');
    statusMessage.textContent = 'Your agreed details were sent to the person who created the link and will be deleted within 10 minutes.';
    showConfirmation(position);
    submitButton.textContent = 'Location shared';
  } catch (error) {
    statusMessage.textContent = `${error.message} Nothing was retained in this page.`;
    submitButton.disabled = false;
  }
}

function showConfirmation(position) {
  resultPanel.replaceChildren();
  resultPanel.hidden = false;
  const note = document.createElement('p');
  note.className = 'location-privacy';
  note.textContent = `Shared latitude ${position.coords.latitude.toFixed(6)}, longitude ${position.coords.longitude.toFixed(6)}. You can close this page.`;
  resultPanel.append(note);
}

function locationError(error) {
  const messages = {
    1: 'You denied browser location permission. Nothing was shared.',
    2: 'Your browser could not determine a location. Nothing was shared.',
    3: 'The location request timed out. Nothing was shared.',
  };
  statusMessage.textContent = messages[error.code] || 'The request failed. Nothing was shared.';
  submitButton.disabled = !shareToken;
}

function browserName(userAgent) {
  if (/Edg\//.test(userAgent)) return 'Microsoft Edge';
  if (/Firefox\//.test(userAgent)) return 'Mozilla Firefox';
  if (/Chrome\//.test(userAgent) && !/Chromium/.test(userAgent)) return 'Google Chrome';
  if (/Safari\//.test(userAgent) && !/Chrome\//.test(userAgent)) return 'Safari';
  return 'Unknown browser';
}