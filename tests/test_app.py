import pytest

import app as site
import utils


def create_location_share(client):
    response = client.post('/api/location-share', json={})
    assert response.status_code == 201
    return response.json


def location_share_payload(share_token, consent=True):
    return {
        'share_token': share_token,
        'consent': consent,
        'coordinates': {'latitude': 10.5, 'longitude': 76.2, 'accuracy': 25.0},
        'device': {
            'browser': 'Example Browser',
            'platform': 'Example OS',
            'model': '',
            'screen': '390 x 844',
            'cpu_cores': '8',
            'user_agent': 'Example Agent',
        },
    }


@pytest.fixture(autouse=True)
def reset_rate_limits():
    site.limiter.reset()
    yield
    site.limiter.reset()


@pytest.fixture
def client():
    site.app.config.update(TESTING=True)
    with site.app.test_client() as test_client:
        yield test_client


def test_homepage_and_health_check(client):
    page = client.get('/')
    location_page = client.get('/my-location')
    share_page = client.get('/share-location')
    health = client.get('/healthz')

    assert page.status_code == 200
    assert b'InfoG' in page.data
    assert location_page.status_code == 200
    assert b'Show my location' in location_page.data
    assert b'does not submit them to the InfoG server' in location_page.data
    assert share_page.status_code == 200
    assert b'Share my location' in share_page.data
    assert b'share-consent' not in share_page.data
    assert share_page.headers['Cache-Control'] == 'no-store'
    assert health.status_code == 200
    assert health.json == {'status': 'ok'}


def test_consent_location_share_owner_flow(client):
    share = create_location_share(client)
    owner_payload = {'owner_token': share['owner_token']}

    waiting = client.post('/api/location-share/status', json=owner_payload)
    assert waiting.status_code == 200
    assert waiting.headers['Cache-Control'] == 'no-store'
    assert waiting.json['result'] is None

    submitted = client.post(
        '/api/location-share/submit',
        json=location_share_payload(share_token_from_url(share['share_url'])),
        environ_base={'REMOTE_ADDR': '203.0.113.9'},
    )
    assert submitted.status_code == 201

    completed = client.post('/api/location-share/status', json=owner_payload)
    assert completed.status_code == 200
    assert completed.json['result']['latitude'] == 10.5
    assert completed.json['result']['request_ip'] == '203.0.113.9'
    assert completed.json['result']['browser'] == 'Example Browser'

    duplicate = client.post(
        '/api/location-share/submit',
        json=location_share_payload(share_token_from_url(share['share_url'])),
    )
    assert duplicate.status_code == 409


def test_location_share_requires_explicit_consent(client):
    share = create_location_share(client)
    payload = location_share_payload(share_token_from_url(share['share_url']), consent=False)

    response = client.post('/api/location-share/submit', json=payload)

    assert response.status_code == 400
    assert 'consent' in response.json['error'].lower()


def test_location_share_rejects_invalid_coordinates(client):
    share = create_location_share(client)
    payload = location_share_payload(share_token_from_url(share['share_url']))
    payload['coordinates']['latitude'] = 999

    response = client.post('/api/location-share/submit', json=payload)

    assert response.status_code == 400


def test_owner_can_delete_location_share(client):
    share = create_location_share(client)

    deleted = client.post('/api/location-share/close', json={'owner_token': share['owner_token']})
    status = client.post('/api/location-share/status', json={'owner_token': share['owner_token']})

    assert deleted.status_code == 200
    assert status.status_code == 404


def test_location_share_expires(client, monkeypatch):
    share = create_location_share(client)
    session_key = next(reversed(site.location_shares))
    monkeypatch.setitem(site.location_shares[session_key], 'expires_at', 0)

    response = client.post('/api/location-share/status', json={'owner_token': share['owner_token']})

    assert response.status_code == 404


def test_dns_record_lookup_collects_both_families(monkeypatch):
    monkeypatch.setattr(
        utils.socket,
        'getaddrinfo',
        lambda *_args: [
            (utils.socket.AF_INET, 1, 6, '', ('203.0.113.7', 0)),
            (utils.socket.AF_INET, 1, 6, '', ('203.0.113.7', 0)),
            (utils.socket.AF_INET6, 1, 6, '', ('2001:db8::7', 0, 0, 0)),
        ],
    )

    result = utils.lookup_domain_records('example.com')

    assert result == {
        'IPv4 addresses': '203.0.113.7',
        'IPv6 addresses': '2001:db8::7',
    }


def test_non_object_json_is_rejected(client):
    response = client.post('/api/lookup', json=['domain', 'example.com'])

    assert response.status_code == 400
    assert 'JSON object' in response.json['error']


def test_domain_lookup_returns_both_address_families(client, monkeypatch):
    monkeypatch.setattr(
        site,
        'lookup_domain_records',
        lambda _hostname: {'IPv4 addresses': '203.0.113.7', 'IPv6 addresses': '2001:db8::7'},
    )

    response = client.post(
        '/api/lookup',
        json={'mode': 'domain', 'value': 'https://example.com/path'},
    )

    assert response.status_code == 200
    assert response.json['result'] == {
        'Domain': 'example.com',
        'IPv4 addresses': '203.0.113.7',
        'IPv6 addresses': '2001:db8::7',
    }


def test_ip_lookup_returns_provider_data(client, monkeypatch):
    monkeypatch.setattr(site, 'lookup_ip', lambda address: {'IPv4': address, 'country_name': 'Example'})

    response = client.post('/api/lookup', json={'mode': 'ip', 'value': '8.8.8.8'})

    assert response.status_code == 200
    assert response.json['result']['country_name'] == 'Example'


def test_phone_lookup_returns_region_and_carrier(client, monkeypatch):
    monkeypatch.setattr(site, 'lookup_phone', lambda _number: ('United States', 'Example Carrier'))

    response = client.post('/api/lookup', json={'mode': 'phone', 'value': '+14155552671'})

    assert response.status_code == 200
    assert response.json['result'] == {
        'Region': 'United States',
        'Service provider': 'Example Carrier',
    }


@pytest.mark.parametrize(
    ('mode', 'value'),
    [
        ('domain', 'not a domain'),
        ('ip', 'not-an-ip'),
        ('ip', '127.0.0.1'),
        ('phone', 'abc'),
        ('other', 'example.com'),
    ],
)
def test_invalid_and_unsupported_lookups_are_rejected(client, mode, value):
    response = client.post('/api/lookup', json={'mode': mode, 'value': value})

    assert response.status_code == 400
    assert 'error' in response.json


def test_lookup_rate_limit_returns_json(client, monkeypatch):
    monkeypatch.setattr(
        site,
        'lookup_domain_records',
        lambda _hostname: {'IPv4 addresses': '203.0.113.7', 'IPv6 addresses': 'No records found'},
    )
    responses = [
        client.post('/api/lookup', json={'mode': 'domain', 'value': 'example.com'})
        for _ in range(16)
    ]

    assert all(response.status_code == 200 for response in responses[:15])
    assert responses[15].status_code == 429
    assert 'Too many lookups' in responses[15].json['error']


def share_token_from_url(url):
    return url.rsplit('#token=', 1)[1]