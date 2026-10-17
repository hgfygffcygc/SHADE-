import ipaddress
import os
import re
import subprocess
import tempfile
from collections import Counter


MAX_PCAP_BYTES = 5 * 1024 * 1024
MAX_CAPTURE_PACKETS = 10_000
MAX_PORT_RANGE = 32
RFC1918_NETWORKS = tuple(map(ipaddress.ip_network, ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')))


def scan_private_host(target, start_port, end_port, nmap_path='nmap'):
    address = ipaddress.ip_address(target)
    if address.version != 4 or not any(address in network for network in RFC1918_NETWORKS):
        raise ValueError('Nmap is limited to one RFC1918 IPv4 address on an authorized private network.')
    if not 1 <= start_port <= end_port <= 65535 or end_port - start_port + 1 > MAX_PORT_RANGE:
        raise ValueError(f'Choose a TCP port range of at most {MAX_PORT_RANGE} ports.')

    command = [
        nmap_path,
        '-n',
        '-Pn',
        '-sT',
        '-T3',
        '--open',
        '--host-timeout',
        '25s',
        '-p',
        f'{start_port}-{end_port}',
        '-oX',
        '-',
        str(address),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError('Nmap check exceeded the 30-second limit.') from error
    if completed.returncode not in (0, 1):
        raise RuntimeError('Nmap could not complete the bounded TCP check.')

    import xml.etree.ElementTree as element_tree

    try:
        root = element_tree.fromstring(completed.stdout)
    except element_tree.ParseError as error:
        raise RuntimeError('Nmap returned an unreadable scan report.') from error

    host = root.find('host')
    if host is None:
        return {'target': str(address), 'ports': [], 'note': 'No host record was returned.'}
    ports = []
    for port in host.findall('./ports/port'):
        state = port.find('state')
        service = port.find('service')
        ports.append({
            'protocol': port.get('protocol', 'tcp'),
            'port': int(port.get('portid', '0')),
            'state': state.get('state', 'unknown') if state is not None else 'unknown',
            'service': service.get('name', 'unknown') if service is not None else 'unknown',
        })
    return {'target': str(address), 'ports': ports, 'note': 'Only the requested TCP port range was checked.'}


def analyze_capture(file_stream, filename, tshark_path='tshark'):
    if not filename or not re.search(r'\.pcap(?:ng)?$', filename, re.IGNORECASE):
        raise ValueError('Upload a .pcap or .pcapng capture file.')

    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(prefix='infog-capture-', suffix='.pcap', delete=False) as capture:
            temporary_path = capture.name
            total = 0
            while True:
                chunk = file_stream.read(64 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_PCAP_BYTES:
                    raise ValueError('Capture files must be 5 MB or smaller.')
                capture.write(chunk)
        if total == 0:
            raise ValueError('The capture file is empty.')

        command = [
            tshark_path,
            '-n',
            '-r',
            temporary_path,
            '-c',
            str(MAX_CAPTURE_PACKETS),
            '-T',
            'fields',
            '-E',
            'separator=/t',
            '-e',
            '_ws.col.Protocol',
            '-e',
            'ip.src',
            '-e',
            'ip.dst',
            '-e',
            'ipv6.src',
            '-e',
            'ipv6.dst',
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if completed.returncode:
            raise ValueError('tshark could not read this capture file.')

        protocols = Counter()
        endpoints = Counter()
        packet_count = 0
        for line in completed.stdout.splitlines()[:MAX_CAPTURE_PACKETS]:
            fields = line.split('\t')
            fields += [''] * (5 - len(fields))
            protocol, *addresses = fields[:5]
            packet_count += 1
            if protocol:
                protocols[protocol[:64]] += 1
            for address in addresses:
                if address:
                    endpoints[address[:128]] += 1

        return {
            'filename': os.path.basename(filename)[:180],
            'packets_analyzed': packet_count,
            'packet_limit': MAX_CAPTURE_PACKETS,
            'protocols': [{'name': name, 'packets': count} for name, count in protocols.most_common(20)],
            'endpoints': [{'address': address, 'packets': count} for address, count in endpoints.most_common(50)],
            'note': 'Offline summary only. Capture contents can contain sensitive data; the temporary upload was deleted after analysis.',
        }
    except subprocess.TimeoutExpired as error:
        raise RuntimeError('Capture analysis exceeded the 15-second limit.') from error
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.remove(temporary_path)