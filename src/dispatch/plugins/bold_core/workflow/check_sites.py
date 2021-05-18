import asyncio
import datetime
import itertools
import logging
import select
import socket
import traceback
from collections import namedtuple
from typing import List

import OpenSSL

logger = logging.getLogger(__name__)
default_expiry_warn = 14


class DomainParseError(Exception):
    pass


class Domain(str):
    def __new__(cls, domain):
        if domain.startswith('!'):
            name = domain[1:]
        else:
            name = domain
        host = name
        port = 443
        if ':' in name:
            host, port = name.split(':')
            try:
                port = int(port)
            except ValueError:
                raise DomainParseError("Couldn't parse '%s', port '%s' is not an integer" % (domain, port))
        connection_host = host
        if '|' in name:
            host, connection_host = name.split('|')
            name = "%s (%s)" % (host, connection_host)
        result = str.__new__(cls, name)
        if domain.startswith('!'):
            result.no_fetch = True
        else:
            result.no_fetch = False
        result.host = host
        result.connection_host = connection_host
        result.port = port
        return result


class CertDomains(list):
    def __init__(self, domain_definitions):
        for d in domain_definitions.split('/'):
            self.append(Domain(d))


def _get_cert_from_domain(domain):
    ctx = OpenSSL.SSL.Context(OpenSSL.SSL.SSLv23_METHOD)
    sock = socket.socket()
    sock.settimeout(5)
    wrapped_sock = OpenSSL.SSL.Connection(ctx, sock)
    wrapped_sock.set_tlsext_host_name(domain.host.encode('ascii'))
    wrapped_sock.connect((domain.connection_host, domain.port))
    while True:
        try:
            wrapped_sock.do_handshake()
            break
        except OpenSSL.SSL.WantReadError:
            select.select([wrapped_sock], [], [])

    return wrapped_sock.get_peer_cert_chain()


def get_cert_from_domain(domain):
    if domain.no_fetch:
        return domain, None
    try:
        data = _get_cert_from_domain(domain)
    except Exception as e:
        data = e
    return domain, data


def get_domain_certs(domains):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    (done, pending) = loop.run_until_complete(asyncio.wait([
        loop.run_in_executor(None, get_cert_from_domain, x)
        for x in itertools.chain(*domains)]))
    loop.close()
    return dict(x.result() for x in done)


def domain_key(d):
    return tuple(reversed(d.split('.')))


def validate_certificate_chain(cert_chain, msgs):
    ctx = OpenSSL.SSL.Context(OpenSSL.SSL.SSLv23_METHOD)
    ctx.set_default_verify_paths()
    cert_store = ctx.get_cert_store()
    for index, cert in reversed(list(enumerate(cert_chain))):
        sc = OpenSSL.crypto.X509StoreContext(cert_store, cert)
        try:
            sc.verify_certificate()
        except OpenSSL.crypto.X509StoreContextError as e:
            msgs.append(
                ('error', "Validation error '%s'." % e))
        if index > 0:
            cert_store.add_cert(cert)


def check(domainnames_certs, utcnow, expiry_warn=default_expiry_warn):
    msgs = []
    domainnames = set(dnc[0].host for dnc in domainnames_certs)
    earliest_expiration = None
    for domain, cert_chain in domainnames_certs:
        if cert_chain is None:
            continue
        if isinstance(cert_chain, Exception):
            cert_chain = "".join(traceback.format_exception_only(type(cert_chain), cert_chain)).strip()
        if not any(isinstance(cert, OpenSSL.crypto.X509) for cert in cert_chain):
            msgs.append(
                ('error', "Couldn't fetch certificate for %s.\n%s" % (domain, cert_chain)))
            continue
        validate_certificate_chain(cert_chain, msgs)
        cert = cert_chain[0]
        expires = datetime.datetime.strptime(cert.get_notAfter().decode('ascii'), '%Y%m%d%H%M%SZ')
        if expires:
            if earliest_expiration is None or expires < earliest_expiration:
                earliest_expiration = expires
        issued_level = "info"
        issuer = cert.get_issuer().commonName
        if issuer.lower() == "happy hacker fake ca":
            issued_level = "error"
        msgs.append(
            (issued_level, "Issued by: %s" % issuer))
        if len(cert_chain) > 1:
            sign_cert = cert_chain[1]
            subject = sign_cert.get_subject().commonName
            if issuer != subject:
                msgs.append(
                    ('error',
                     "The certificate sign chain subject '%s' doesn't match the issuer '%s'." % (subject, issuer)))
        sig_alg = cert.get_signature_algorithm()
        if sig_alg.startswith(b'sha1'):
            msgs.append(
                ('error', "Unsecure signature algorithm %s" % sig_alg))
        if expires < utcnow:
            msgs.append(
                ('error', "The certificate has expired on %s." % expires))
        elif expires < (utcnow + datetime.timedelta(days=expiry_warn)):
            msgs.append(
                ('warning', "The certificate expires on %s (%s)." % (
                    expires, expires - utcnow)))
        else:
            # rounded delta
            delta = ((expires - utcnow) // 60 // 10 ** 6) * 60 * 10 ** 6
            msgs.append(
                ('info', "Valid until %s (%s)." % (expires, delta)))
        alt_names = set()
        for index in range(cert.get_extension_count()):
            ext = cert.get_extension(index)
            if ext.get_short_name() != b'subjectAltName':
                continue
            alt_names.update(
                x.strip().replace('DNS:', '')
                for x in str(ext).split(','))
        alt_names.add(cert.get_subject().commonName)
        unmatched = domainnames.difference(alt_names)
        if unmatched:
            msgs.append(
                ('info', "Alternate names in certificate: %s" % ', '.join(
                    sorted(alt_names, key=domain_key))))
            if len(domainnames) == 1:
                name = cert.get_subject().commonName
                if name != domain.host:
                    if name.startswith('*.'):
                        name_parts = name.split('.')[1:]
                        name_parts_len = len(name_parts)
                        domain_host_parts = domain.host.split('.')
                        if (len(domain_host_parts) - name_parts_len) == 1:
                            if domain_host_parts[-name_parts_len:] == name_parts:
                                continue
                    msgs.append(
                        ('error', "The requested domain %s doesn't match the certificate domain %s." % (domain, name)))
            else:
                msgs.append(
                    ('warning', "Unmatched alternate names %s." % ', '.join(
                        sorted(unmatched, key=domain_key))))
        elif domainnames == alt_names:
            msgs.append(
                ('info', "Alternate names match specified domains."))
        else:
            unmatched = alt_names.difference(domainnames)
            msgs.append(
                ('warning', "More alternate names than specified %s." % ', '.join(
                    sorted(unmatched, key=domain_key))))
    return (msgs, earliest_expiration)


def check_domains(domains, domain_certs, utcnow, expiry_warn=default_expiry_warn):
    result = []
    for domainnames in domains:
        domainnames_certs = [(dn, domain_certs[dn]) for dn in domainnames]
        msgs = []
        seen = set()
        earliest_expiration = None
        (dmsgs, expiration) = check(domainnames_certs, utcnow, expiry_warn=expiry_warn)
        for level, msg in dmsgs:
            if expiration:
                if earliest_expiration is None or expiration < earliest_expiration:
                    earliest_expiration = expiration
            if msg not in seen:
                seen.add(msg)
                msgs.append((level, msg))
        result.append((domainnames, msgs, earliest_expiration))

    return result


def domain_definitions_from_cli(domains):
    result = []
    if not domains:
        return result
    for domain in domains:
        try:
            domain_definition = CertDomains(domain)
        except DomainParseError as e:
            logger.error("Error in definition '%s': %s" % (domain, e))
        result.append(domain_definition)
    return result


def process_domains(servers: List[str], expiry_warn: int, verbose: bool = False):
    """Checks the TLS certificate for each DOMAIN.
       You can add checks for alternative names by separating them with a slash, like example.com/www.example.com.
       Wildcard domains are supported.
       Exits with return code 3 when there are warnings, code 4 when there are errors and code 5 when the domain definition contains errors.
    """
    domains = list(itertools.chain(
        domain_definitions_from_cli(servers)))
    domain_certs = get_domain_certs(domains)

    total_warnings = 0
    total_errors = 0
    earliest_expiration = None
    utcnow = datetime.datetime.utcnow()
    checked_domains = check_domains(domains, domain_certs, utcnow, expiry_warn=expiry_warn)

    elements = []
    domain_msgs = ""

    for domainnames, msgs, expiration in checked_domains:
        if expiration:
            if earliest_expiration is None or expiration < earliest_expiration:
                earliest_expiration = expiration
        warnings = 0
        errors = 0
        domain_msgs = f"{domain_msgs}\n{', '.join(domainnames)}"

        for level, msg in msgs:
            if level == 'error':
                errors = errors + 1
            elif level == 'warning':
                warnings = warnings + 1
            msg = "\n".join("    " + m for m in msg.split('\n'))
            domain_msgs = f"{domain_msgs}\n{msg}"

        total_errors = total_errors + errors
        total_warnings = total_warnings + warnings

    elements.append({
        "type": "mrkdwn",
        "text": f"{domain_msgs}"
        }
    )

    msg = "_%s *error(s)*, %s *warning(s)*_" % (total_errors, total_warnings)

    if earliest_expiration:
        msg += "\n_Earliest expiration on_ *%s (%s).*" % (
            earliest_expiration, earliest_expiration - utcnow)

    elements.append({
        "type": "mrkdwn",
        "text": f"{msg}"
        }
    )

    return [
        {
            "type": "context",
            "elements": elements
        }
    ]


# Main
def get_sites_info():

    servers = [
        'payments.api.bold.co',
        'checkout.bold.co',
        'terminals.api.bold.co',
        'reports.api.bold.co',
        'security.api.bold.co',
        'merchants.api.bold.co',
        'accounting.api.bold.co',
        'events.accounting.bold.co'
    ]

    return process_domains(servers=servers, expiry_warn=14, verbose=False)
