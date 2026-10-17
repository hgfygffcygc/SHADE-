import json
import threading

import pytest
from werkzeug.serving import make_server

import app as site


@pytest.fixture(scope='module')
def live_server():
    server = make_server('127.0.0.1', 0, site.app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{server.server_port}'
    server.shutdown()
    thread.join(timeout=5)


@pytest.fixture(scope='module')
def browser():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        instance = playwright.chromium.launch()
        yield instance
        instance.close()


def test_lookup_shows_provenance_and_downloads_report(live_server, browser, tmp_path):
    page = browser.new_page(accept_downloads=True)
    page.route(
        '**/api/lookup',
        lambda route: route.fulfill(
            status=200,
            content_type='application/json',
            body=json.dumps({
                'result': {'A': ['203.0.113.10'], 'MX': ['10 mail.example.test']},
                'report': {
                    'query': 'example.test',
                    'mode': 'dns',
                    'source': 'Test recursive resolver',
                    'queried_at': '2026-01-01T00:00:00+00:00',
                    'caveat': 'Public DNS data may be cached.',
                },
            }),
        ),
    )

    page.goto(live_server, wait_until='domcontentloaded')
    page.get_by_role('tab', name='DNS').click()
    page.get_by_label('Domain name').fill('example.test')
    page.get_by_role('button', name='Look up').click()

    page.get_by_text('203.0.113.10').wait_for()
    assert page.locator('#report-source').inner_text() == 'Test recursive resolver'
    assert 'Public DNS data may be cached.' in page.locator('#report-caveat').inner_text()

    with page.expect_download() as json_download:
        page.get_by_role('button', name='JSON').click()
    json_path = tmp_path / 'lookup.json'
    json_download.value.save_as(json_path)
    report = json.loads(json_path.read_text(encoding='utf-8'))
    assert report['report']['source'] == 'Test recursive resolver'
    assert report['result']['A'] == ['203.0.113.10']

    with page.expect_download() as csv_download:
        page.get_by_role('button', name='CSV').click()
    csv_path = tmp_path / 'lookup.csv'
    csv_download.value.save_as(csv_path)
    csv_report = csv_path.read_text(encoding='utf-8')
    assert 'Test recursive resolver' in csv_report
    assert 'Public DNS data may be cached.' in csv_report
    page.close()


def test_location_request_occurs_only_after_button_press(live_server, browser):
    context = browser.new_context(
        permissions=['geolocation'],
        geolocation={'latitude': 10.5, 'longitude': 76.2, 'accuracy': 20},
    )
    page = context.new_page()
    submissions = []

    def capture_submission(route):
        submissions.append(json.loads(route.request.post_data))
        route.fulfill(status=201, content_type='application/json', body='{"status":"shared"}')

    page.route('**/api/location-share/submit', capture_submission)
    page.goto(f'{live_server}/share-location#token=e2e-share-token', wait_until='domcontentloaded')
    assert page.get_by_role('button', name='Share my location').is_enabled()
    assert submissions == []

    page.get_by_role('button', name='Share my location').click()
    page.get_by_text('Your agreed details were sent', exact=False).wait_for()

    assert len(submissions) == 1
    assert submissions[0]['consent'] is True
    assert submissions[0]['coordinates']['latitude'] == 10.5
    assert page.url.endswith('/share-location')
    context.close()
