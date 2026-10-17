import ipaddress
import logging
import math
import os
import re
import secrets
import threading
import time
from urllib.parse import urlsplit

import phonenumbers
import requests
from flask import Flask, jsonify, render_template, request
from flask_limiter import Limiter
from flask_limiter.errors import RateLimitExceeded
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix

from utils import lookup_domain_records, lookup_ip, lookup_phone

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
app.logger.setLevel(logging.INFO)

limiter = Limiter(
    get_remote_address,
    app=app,
    storage_uri=os.environ.get('RATELIMIT_STORAGE_URI', 'memory://'),
)
LOCATION_SHARE_TTL_SECONDS = 10 * 60
location_shares = {}
location_shares_lock = threading.Lock()


def normalize_domain(value):
    value = value.strip()
    if not value or len(value) > 2048:
        raise ValueError('Enter a valid domain name.')

    parsed = urlsplit(value if '://' in value else f'//{value}')
    hostname = parsed.hostname
    if not hostname:
        raise ValueError('Enter a valid domain name, such as example.com.')

    try:
        hostname = hostname.rstrip('.').encode('idna').decode('ascii')
    except UnicodeError as error:
        raise ValueError('That domain name is not valid.') from error

    if len(hostname) > 253 or not all(
        re.fullmatch(r'[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?', label)
        for label in hostname.split('.')
    ):
        raise ValueError('Enter a valid domain name, such as example.com.')
    return hostname


@app.get('/')
def index():
    return render_template('index.html')


@app.get('/my-location')
def my_location():
    return render_template('my_location.html')


@app.get('/share-location')
def share_location():
    response = app.make_response(render_template('share_location.html'))
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Referrer-Policy'] = 'no-referrer'
    return response


@app.after_request
def protect_location_share_responses(response):
    if request.path.startswith('/api/location-share'):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Referrer-Policy'] = 'no-referrer'
    return response


def prune_location_shares(now=None):
    now = now or time.time()
    expired = [
        share_id
        for share_id, session in location_shares.items()
        if session['expires_at'] <= now
    ]
    for share_id in expired:
        del location_shares[share_id]


def get_location_share(token, token_type):
    with location_shares_lock:
        prune_location_shares()
        for session in location_shares.values():
            if secrets.compare_digest(session[token_type], token):
                return session
    return None


@app.post('/api/location-share')
@limiter.limit('5 per hour')
def create_location_share():
    now = time.time()
    with location_shares_lock:
        prune_location_shares(now)
        share_id = secrets.token_urlsafe(16)
        while share_id in location_shares:
            share_id = secrets.token_urlsafe(16)
        location_shares[share_id] = {
            'owner_token': secrets.token_urlsafe(32),
            'share_token': secrets.token_urlsafe(32),
            'expires_at': now + LOCATION_SHARE_TTL_SECONDS,
            'result': None,
        }
        session = location_shares[share_id]

    return jsonify(
        owner_token=session['owner_token'],
        share_url=f'{request.url_root.rstrip("/")}/share-location#token={session["share_token"]}',
        expires_in=LOCATION_SHARE_TTL_SECONDS,
    ), 201


@app.post('/api/location-share/status')
@limiter.limit('30 per minute')
def location_share_status():
    payload = request.get_json(silent=True)
    owner_token = payload.get('owner_token') if isinstance(payload, dict) else None
    if not isinstance(owner_token, str) or len(owner_token) > 128:
        return jsonify(error='Invalid or expired share session.'), 404

    session = get_location_share(owner_token, 'owner_token')
    if session is None:
        return jsonify(error='This share link has expired or was deleted.'), 404
    return jsonify(
        expires_in=max(0, int(session['expires_at'] - time.time())),
        result=session['result'],
    )


@app.post('/api/location-share/submit')
@limiter.limit('5 per minute')
def submit_location_share():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or payload.get('consent') is not True:
        return jsonify(error='Explicit consent is required before sharing.'), 400

    share_token = payload.get('share_token')
    coords = payload.get('coordinates')
    device = payload.get('device')
    if not isinstance(share_token, str) or len(share_token) > 128:
        return jsonify(error='This share link has expired or is invalid.'), 404
    if not isinstance(coords, dict) or not isinstance(device, dict):
        return jsonify(error='The location details are incomplete.'), 400

    latitude = coords.get('latitude')
    longitude = coords.get('longitude')
    accuracy = coords.get('accuracy')
    numeric_values = (latitude, longitude, accuracy)
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in numeric_values):
        return jsonify(error='The location coordinates are invalid.'), 400
    if (
        not all(math.isfinite(value) for value in numeric_values)
        or not -90 <= latitude <= 90
        or not -180 <= longitude <= 180
        or not 0 <= accuracy <= 10_000_000
    ):
        return jsonify(error='The location coordinates are invalid.'), 400

    allowed_device_fields = ('browser', 'platform', 'model', 'screen', 'cpu_cores', 'user_agent')
    if any(
        not isinstance(device.get(field, ''), str) or len(device.get(field, '')) > 512
        for field in allowed_device_fields
    ):
        return jsonify(error='The device details are invalid.'), 400

    result = {
        'latitude': round(latitude, 6),
        'longitude': round(longitude, 6),
        'accuracy_meters': round(accuracy),
        'shared_at': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime()),
        'request_ip': request.remote_addr or 'Not available',
        **{field: device.get(field) or 'Not provided' for field in allowed_device_fields},
    }
    with location_shares_lock:
        prune_location_shares()
        session = next(
            (
                candidate for candidate in location_shares.values()
                if secrets.compare_digest(candidate['share_token'], share_token)
            ),
            None,
        )
        if session is None:
            return jsonify(error='This share link has expired or was already used.'), 404
        if session['result'] is not None:
            return jsonify(error='These details have already been shared.'), 409
        session['result'] = result

    return jsonify(status='shared'), 201


@app.post('/api/location-share/close')
@limiter.limit('10 per minute')
def close_location_share():
    payload = request.get_json(silent=True)
    owner_token = payload.get('owner_token') if isinstance(payload, dict) else None
    if not isinstance(owner_token, str) or len(owner_token) > 128:
        return jsonify(error='Invalid or expired share session.'), 404

    with location_shares_lock:
        prune_location_shares()
        share_id = next(
            (
                key for key, session in location_shares.items()
                if secrets.compare_digest(session['owner_token'], owner_token)
            ),
            None,
        )
        if share_id is None:
            return jsonify(error='This share link has expired or was already deleted.'), 404
        del location_shares[share_id]

    return jsonify(status='deleted')


@app.get('/healthz')
def health_check():
    return jsonify(status='ok')


@app.errorhandler(RateLimitExceeded)
def rate_limit_exceeded(_error):
    return jsonify(error='Too many lookups. Please wait a minute and try again.'), 429


@app.post('/api/lookup')
@limiter.limit('15 per minute; 300 per day')
def api_lookup():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error='Send a JSON object containing the lookup type and value.'), 400
    mode = payload.get('mode')
    value = payload.get('value', '')
    if not isinstance(value, str) or len(value) > 2048:
        return jsonify(error='Enter a valid value to look up.'), 400

    try:
        if mode == 'domain':
            hostname = normalize_domain(value)
            result = {'Domain': hostname, **lookup_domain_records(hostname)}
        elif mode == 'ip':
            address = str(ipaddress.ip_address(value.strip()))
            if not ipaddress.ip_address(address).is_global:
                return jsonify(error='Enter a public IP address.'), 400
            result = lookup_ip(address)
        elif mode == 'phone':
            number = phonenumbers.parse(value.strip())
            if not phonenumbers.is_valid_number(number):
                return jsonify(error='Enter a valid phone number with its country code.'), 400
            region, carrier = lookup_phone(value)
            result = {'Region': region or 'Unknown', 'Service provider': carrier or 'Unknown'}
        else:
            return jsonify(error='Choose a supported lookup type.'), 400
    except phonenumbers.NumberParseException:
        return jsonify(error='Enter a valid phone number with its country code.'), 400
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except (OSError, requests.RequestException):
        app.logger.warning('Lookup provider failed for mode %s', mode, exc_info=True)
        return jsonify(error='The lookup service could not be reached. Please try again.'), 502

    return jsonify(result=result)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)