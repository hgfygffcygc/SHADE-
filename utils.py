import ipaddress
import socket
import ssl
from datetime import datetime, timezone

import dns.exception
import dns.resolver
import phonenumbers
import requests
from phonenumbers import carrier
from phonenumbers import geocoder
import os 
import platform

def lookup_domain(domain):
    return socket.gethostbyname(domain.strip())


def lookup_domain_records(domain):
    records = {'IPv4 addresses': set(), 'IPv6 addresses': set()}
    for family, _socktype, _protocol, _canonical_name, address in socket.getaddrinfo(
        domain.strip(), None, socket.AF_UNSPEC, socket.SOCK_STREAM
    ):
        parsed_address = ipaddress.ip_address(address[0])
        key = 'IPv4 addresses' if family == socket.AF_INET else 'IPv6 addresses'
        records[key].add(str(parsed_address))

    return {
        key: ', '.join(sorted(addresses)) or 'No records found'
        for key, addresses in records.items()
    }


def lookup_dns_records(domain):
    resolver = dns.resolver.Resolver()
    resolver.timeout = 2
    resolver.lifetime = 5
    record_types = ('A', 'AAAA', 'MX', 'NS', 'TXT', 'CAA')
    records = {}

    for record_type in record_types:
        try:
            answers = resolver.resolve(domain, record_type, lifetime=5)
            records[record_type] = [str(answer).strip('"')[:240] for answer in answers[:15]]
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            records[record_type] = []
        except (dns.resolver.NoNameservers, dns.exception.Timeout):
            records[record_type] = []

    return records


def lookup_rdap(target, target_type):
    response = requests.get(
        f'https://rdap.org/{target_type}/{target}',
        headers={'Accept': 'application/rdap+json, application/json'},
        timeout=(3, 8),
    )
    response.raise_for_status()
    data = response.json()
    result = {'Query': target, 'Query type': target_type.upper()}

    if target_type == 'domain':
        result.update({
            'Domain name': data.get('ldhName'),
            'Handle': data.get('handle'),
            'Status': ', '.join(data.get('status', [])[:10]),
            'Nameservers': ', '.join(
                server.get('ldhName', '') for server in data.get('nameservers', [])[:20]
            ),
            'Events': '; '.join(
                f"{event.get('eventAction', 'event')}: {event.get('eventDate', '')}"
                for event in data.get('events', [])[:10]
            ),
        })
    else:
        result.update({
            'Network name': data.get('name'),
            'Handle': data.get('handle'),
            'Network range': ' - '.join(
                part for part in (data.get('startAddress'), data.get('endAddress')) if part
            ),
            'Country': data.get('country'),
            'Network type': data.get('type'),
            'Status': ', '.join(data.get('status', [])[:10]),
            'Events': '; '.join(
                f"{event.get('eventAction', 'event')}: {event.get('eventDate', '')}"
                for event in data.get('events', [])[:10]
            ),
        })

    return {key: value for key, value in result.items() if value}


def lookup_tls_certificate(domain):
    context = ssl.create_default_context()
    addresses = socket.getaddrinfo(domain, 443, socket.AF_UNSPEC, socket.SOCK_STREAM)
    last_error = None

    for family, _socktype, _protocol, _canonical_name, address in addresses:
        ip_address = ipaddress.ip_address(address[0])
        if not ip_address.is_global:
            continue

        try:
            with socket.create_connection((str(ip_address), 443), timeout=5) as raw_socket:
                with context.wrap_socket(raw_socket, server_hostname=domain) as tls_socket:
                    certificate = tls_socket.getpeercert()
                    not_after = certificate.get('notAfter')
                    valid_until = None
                    if not_after:
                        expiry = datetime.strptime(not_after, '%b %d %H:%M:%S %Y %Z')
                        valid_until = expiry.replace(tzinfo=timezone.utc).isoformat()
                    return {
                        'Hostname': domain,
                        'TLS version': tls_socket.version() or 'Unknown',
                        'Cipher': (tls_socket.cipher() or ('Unknown',))[0],
                        'Certificate subject': ', '.join(
                            f'{key}={value}'
                            for group in certificate.get('subject', ())
                            for key, value in group
                        ) or 'Unavailable',
                        'Certificate issuer': ', '.join(
                            f'{key}={value}'
                            for group in certificate.get('issuer', ())
                            for key, value in group
                        ) or 'Unavailable',
                        'Valid until': valid_until or 'Unavailable',
                        'Subject alternative names': ', '.join(
                            value for kind, value in certificate.get('subjectAltName', ())
                            if kind == 'DNS'
                        )[:1000] or 'Unavailable',
                    }
        except (OSError, ssl.SSLError, ValueError) as error:
            last_error = error

    raise ValueError('Could not connect to a public HTTPS service for this hostname.') from last_error


def lookup_ip(ip_address):
    response = requests.get(
        f"https://geolocation-db.com/json/{ip_address.strip()}&position=true",
        timeout=12,
    )
    response.raise_for_status()
    return response.json()


def lookup_phone(phone_number):
    parsed_number = phonenumbers.parse(phone_number.strip())
    return (
        geocoder.description_for_number(parsed_number, 'en'),
        carrier.name_for_number(parsed_number, 'en'),
    )


def tool_name():
    print('''
 ___                                               ____________
|%%%|                                             |@@@@@@@@@@@@|
|%%%|  ____       ___   _________   ____________  |@@@@________|       
|%%%| |%%%%\     |%%%| |%%% _____| |%%%______%%%| |@@@|
|%%%| |%%%%%\    |%%%| |%%%|_____  |%%|      |%%| |@@@|       ___
|%%%| |%%%%%%\   |%%%| |%%%_____|  |%%|      |%%| |@@@|      |@@@|
|%%%| |%%%|\%%\  |%%%| |%%%|       |%%|      |%%| |@@@|______|@@@|
|%%%| |%%%| \%%\ |%%%| |%%%|       |%%|______|%%| |@@@@@@@@@@@@@@|
|___| |___|  \_______| |___|       |____________| |______________|By: Tech-Sec
For more visit: https://github/Tech-Sec
''')


def domain_name():
    print(lookup_domain(input('Domain name: ')))


def your_ip():
    your_ip=requests.get('https://geolocation-db.com/json/').json() 
    print('Your public IP address: ',your_ip.get('IPv4'))
    hostname = socket.gethostname()
    ip_address = socket.gethostbyname(hostname)
    print('Your device name: ',hostname)
    print('Your private IP address ',ip_address)


def ip_lookup():
    enter_ip = input('IP Address: ')
    for key, value in lookup_ip(enter_ip).items():
        print(key, ' : ', value)


def ph_num_lookup():
    your_ph_num = input('Your Number: ')
    region, service_provider = lookup_phone(your_ph_num)
    print(region)
    print(service_provider)
    
    
def ip_grabber():
    if platform.system() == 'Windows':
        print('IP-Grabber is not supported on Windows')
    else:
        os.system('cd IP-Grabber && sudo chmod 777 * && bash ip-grabber.sh')
