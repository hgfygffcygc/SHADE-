import ipaddress
import socket
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
