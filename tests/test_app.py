import io

import pytest
import fakeredis

import app as site
import utils
import network_tools


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
    assert b'data-mode="dns"' in page.data
    assert b'data-mode="rdap"' in page.data
    assert b'data-mode="tls"' in page.data
    assert location_page.status_code == 200
    assert b'Show my location' in location_page.data
    assert b'does not submit them to the InfoG server' in location_page.data
    assert share_page.status_code == 200
    assert b'Share my location' in share_page.data
    assert b'share-consent' not in share_page.data
    assert share_page.headers['Cache-Control'] == 'no-store'
    assert health.status_code == 200
    assert health.json == {'status': 'ok'}
    assert page.headers['X-Content-Type-Options'] == 'nosniff'
    assert page.headers['X-Frame-Options'] == 'DENY'
    assert page.headers['Referrer-Policy'] == 'no-referrer'
    assert "frame-ancestors 'none'" in page.headers['Content-Security-Policy']
    assert 'geolocation=(self)' in page.headers['Permissions-Policy']
    assert page.headers['Cross-Origin-Opener-Policy'] == 'same-origin'
    assert page.headers.get('Strict-Transport-Security') is None
    assert page.headers['X-Content-Type-Options'] == 'nosniff'


def test_hsts_is_only_sent_for_secure_requests(client):
    response = client.get('/', base_url='https://localhost')

    assert response.headers['Strict-Transport-Security'].startswith('max-age=31536000')


def test_network_diagnostics_page_and_apis_are_disabled_by_default(client, monkeypatch):
    monkeypatch.setattr(site, 'ENABLE_NMAP', False)
    monkeypatch.setattr(site, 'ENABLE_PCAP_ANALYSIS', False)
    monkeypatch.setattr(site, 'NMAP_PATH', None)
    monkeypatch.setattr(site, 'TSHARK_PATH', None)

    page = client.get('/network-tools')
    nmap = client.post('/api/network/nmap', json={})
    pcap = client.post('/api/network/pcap', data={})

    assert page.status_code == 200
    assert b'Nmap is disabled or unavailable' in page.data
    assert nmap.status_code == 503
    assert pcap.status_code == 503


def test_nmap_route_requires_explicit_authorization(client, monkeypatch):
    monkeypatch.setattr(site, 'ENABLE_NMAP', True)
    monkeypatch.setattr(site, 'NMAP_PATH', 'nmap')

    response = client.post('/api/network/nmap', json={'target': '192.168.1.20', 'start_port': 80, 'end_port': 80})

    assert response.status_code == 400
    assert 'authorization' in response.json['error'].lower()


def test_nmap_route_validates_scope_and_returns_bounded_result(client, monkeypatch):
    monkeypatch.setattr(site, 'ENABLE_NMAP', True)
    monkeypatch.setattr(site, 'NMAP_PATH', 'nmap')
    monkeypatch.setattr(
        site,
        'scan_private_host',
        lambda target, start, end, _path: {
            'target': target,
            'ports': [{'protocol': 'tcp', 'port': start, 'state': 'open', 'service': 'http'}],
            'note': f'Only ports {start}-{end}',
        },
    )

    response = client.post('/api/network/nmap', json={
        'target': '192.168.1.20', 'start_port': 80, 'end_port': 80, 'authorized': True,
    })

    assert response.status_code == 200
    assert response.json['result']['target'] == '192.168.1.20'


def test_pcap_endpoint_requires_upload_consent(client, monkeypatch):
    monkeypatch.setattr(site, 'ENABLE_PCAP_ANALYSIS', True)
    monkeypatch.setattr(site, 'TSHARK_PATH', 'tshark')

    response = client.post('/api/network/pcap', data={})

    assert response.status_code == 400


def test_network_tools_refuse_public_origin_even_if_enabled(client, monkeypatch):
    monkeypatch.setattr(site, 'PUBLIC_BASE_URL', 'https://infog.example.test')
    monkeypatch.setattr(site, 'ENABLE_NMAP', True)
    monkeypatch.setattr(site, 'ENABLE_PCAP_ANALYSIS', True)
    monkeypatch.setattr(site, 'NMAP_PATH', 'nmap')
    monkeypatch.setattr(site, 'TSHARK_PATH', 'tshark')

    page = client.get('/network-tools')
    nmap = client.post('/api/network/nmap', json={'authorized': True})
    pcap = client.post('/api/network/pcap', data={})

    assert b'Nmap is disabled' in page.data
    assert b'Offline capture analysis is disabled' in page.data
    assert nmap.status_code == 503
    assert pcap.status_code == 503


def test_share_link_rejects_unconfigured_public_host(client, monkeypatch):
    monkeypatch.setattr(site, 'PUBLIC_BASE_URL', '')

    response = client.post('/api/location-share', json={}, base_url='https://attacker.example')

    assert response.status_code == 400
    assert 'PUBLIC_BASE_URL' in response.json['error']


def test_share_link_uses_configured_public_origin(client, monkeypatch):
    monkeypatch.setattr(site, 'PUBLIC_BASE_URL', 'https://infog.example.test')

    response = client.post('/api/location-share', json={}, base_url='http://attacker.example')

    assert response.status_code == 201
    assert response.json['share_url'].startswith('https://infog.example.test/')


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


def test_location_share_uses_shared_redis_backend(client, monkeypatch):
    fake_redis = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(site, 'redis_client', fake_redis)

    share = create_location_share(client)
    share_token = share_token_from_url(share['share_url'])
    waiting = client.post('/api/location-share/status', json={'owner_token': share['owner_token']})
    submitted = client.post(
        '/api/location-share/submit',
        json=location_share_payload(share_token),
    )
    duplicate = client.post(
        '/api/location-share/submit',
        json=location_share_payload(share_token),
    )
    completed = client.post('/api/location-share/status', json={'owner_token': share['owner_token']})
    deleted = client.post('/api/location-share/close', json={'owner_token': share['owner_token']})
    expired = client.post('/api/location-share/status', json={'owner_token': share['owner_token']})

    assert waiting.status_code == 200 and waiting.json['result'] is None
    assert submitted.status_code == 201
    assert duplicate.status_code == 409
    assert completed.json['result']['latitude'] == 10.5
    assert deleted.status_code == 200
    assert expired.status_code == 404


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


def test_rdap_helper_returns_public_domain_fields_only(monkeypatch):
    class MockResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                'ldhName': 'example.com',
                'handle': 'EXAMPLE',
                'status': ['active'],
                'nameservers': [{'ldhName': 'ns1.example.com'}],
                'events': [{'eventAction': 'registration', 'eventDate': '2020-01-01'}],
                'entities': [{'vcardArray': ['vcard', [['fn', {}, 'text', 'Private Person']]]}],
            }

    monkeypatch.setattr(utils.requests, 'get', lambda *_args, **_kwargs: MockResponse())

    result = utils.lookup_rdap('example.com', 'domain')

    assert result['Domain name'] == 'example.com'
    assert result['Nameservers'] == 'ns1.example.com'
    assert 'Private Person' not in str(result)


def test_tls_helper_refuses_non_public_resolved_addresses(monkeypatch):
    monkeypatch.setattr(
        utils.socket,
        'getaddrinfo',
        lambda *_args: [(utils.socket.AF_INET, 1, 6, '', ('127.0.0.1', 443))],
    )

    with pytest.raises(ValueError, match='public HTTPS service'):
        utils.lookup_tls_certificate('localhost')


@pytest.mark.parametrize('target', ['8.8.8.8', '127.0.0.1', '169.254.1.2', '2001:4860:4860::8888'])
def test_nmap_helper_rejects_out_of_scope_targets(target):
    with pytest.raises(ValueError):
        network_tools.scan_private_host(target, 80, 80)


def test_nmap_helper_limits_range_and_uses_argument_list(monkeypatch):
    calls = []

    class Completed:
        returncode = 0
        stdout = '<nmaprun><host><ports><port protocol="tcp" portid="443"><state state="open"/><service name="https"/></port></ports></host></nmaprun>'

    monkeypatch.setattr(network_tools.subprocess, 'run', lambda command, **kwargs: calls.append((command, kwargs)) or Completed())

    result = network_tools.scan_private_host('192.168.1.12', 443, 443, 'nmap')

    assert result['ports'][0]['port'] == 443
    command, kwargs = calls[0]
    assert command[-1] == '192.168.1.12'
    assert '-p' in command and '443-443' in command
    assert kwargs['shell'] is False if 'shell' in kwargs else True
    with pytest.raises(ValueError, match='at most'):
        network_tools.scan_private_host('192.168.1.12', 1, 100, 'nmap')


def test_capture_analysis_caps_packets_and_deletes_temporary_file(monkeypatch, tmp_path):
    real_named_temp = network_tools.tempfile.NamedTemporaryFile

    def named_temp(*args, **kwargs):
        kwargs['dir'] = tmp_path
        return real_named_temp(*args, **kwargs)

    class Completed:
        returncode = 0
        stdout = 'DNS\t192.0.2.10\t192.0.2.53\t\t\nTCP\t192.0.2.10\t192.0.2.53\t\t\n'

    monkeypatch.setattr(network_tools.tempfile, 'NamedTemporaryFile', named_temp)
    monkeypatch.setattr(network_tools.subprocess, 'run', lambda *_args, **_kwargs: Completed())

    result = network_tools.analyze_capture(io.BytesIO(b'pcap sample'), 'capture.pcap', 'tshark')

    assert result['packets_analyzed'] == 2
    assert result['protocols'][0] == {'name': 'DNS', 'packets': 1}
    assert list(tmp_path.iterdir()) == []


def test_capture_analysis_rejects_oversized_file():
    oversized = io.BytesIO(b'x' * (network_tools.MAX_PCAP_BYTES + 1))

    with pytest.raises(ValueError, match='5 MB or smaller'):
        network_tools.analyze_capture(oversized, 'large.pcap', 'tshark')


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


def test_dns_lookup_returns_public_record_types(client, monkeypatch):
    monkeypatch.setattr(
        site,
        'lookup_dns_records',
        lambda _hostname: {'A': ['203.0.113.7'], 'MX': ['10 mail.example.com.']},
    )

    response = client.post('/api/lookup', json={'mode': 'dns', 'value': 'example.com'})

    assert response.status_code == 200
    assert response.json['result']['Domain'] == 'example.com'
    assert response.json['result']['A'] == ['203.0.113.7']


def test_rdap_domain_lookup_returns_registry_summary(client, monkeypatch):
    monkeypatch.setattr(
        site,
        'lookup_rdap',
        lambda _target, _kind: {'Domain name': 'example.com', 'Status': 'active'},
    )

    response = client.post('/api/lookup', json={'mode': 'rdap', 'value': 'example.com'})

    assert response.status_code == 200
    assert response.json['result']['Domain name'] == 'example.com'


def test_rdap_ip_lookup_uses_public_ip_registry(client, monkeypatch):
    monkeypatch.setattr(
        site,
        'lookup_rdap',
        lambda target, kind: {'Query': target, 'Query type': kind.upper()},
    )

    response = client.post('/api/lookup', json={'mode': 'rdap', 'value': '8.8.8.8'})

    assert response.status_code == 200
    assert response.json['result']['Query type'] == 'IP'


def test_rdap_rejects_private_ip(client):
    response = client.post('/api/lookup', json={'mode': 'rdap', 'value': '192.168.1.1'})

    assert response.status_code == 400


def test_tls_lookup_returns_certificate_summary(client, monkeypatch):
    monkeypatch.setattr(
        site,
        'lookup_tls_certificate',
        lambda _hostname: {'Hostname': 'example.com', 'TLS version': 'TLSv1.3'},
    )

    response = client.post('/api/lookup', json={'mode': 'tls', 'value': 'example.com'})

    assert response.status_code == 200
    assert response.json['result']['TLS version'] == 'TLSv1.3'


def test_ip_lookup_returns_provider_data(client, monkeypatch):
    monkeypatch.setattr(site, 'lookup_ip', lambda address: {'IPv4': address, 'country_name': 'Example'})

    response = client.post('/api/lookup', json={'mode': 'ip', 'value': '8.8.8.8'})

    assert response.status_code == 200
    assert response.json['result']['country_name'] == 'Example'
    assert response.json['report']['source'] == 'geolocation-db.com'
    assert response.json['report']['query'] == '8.8.8.8'
    assert response.json['report']['queried_at'].endswith('+00:00')
    assert 'approximate' in response.json['report']['caveat']


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