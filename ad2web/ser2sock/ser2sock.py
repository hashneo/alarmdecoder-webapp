import os

import ConfigParser
import psutil
import signal
from OpenSSL import crypto

from ..certificate.models import Certificate
from ..certificate.constants import CRL_CODE, ACTIVE, REVOKED, CA

DEFAULT_SETTINGS = {
    'device': '',
    'baudrate': 19200,
    'port': 10000,
    'preserve_connections': '1',
    'encrypted': '0',
    'ca_certificate': '',
    'ssl_certificate': '',
    'ssl_key': ''
}

def read_config(path):
    config = ConfigParser.SafeConfigParser()
    config.read(path)

    return config

def save_config(path, config_values=DEFAULT_SETTINGS):
    config = read_config(path)

    try:
        config.add_section('ser2sock')
    except ConfigParser.DuplicateSectionError:
        pass

    for k, v in config_values.iteritems():
        config.set('ser2sock', k, str(v))

    with open(path, 'w') as configfile:
        config.write(configfile)

def hup():
    for proc in psutil.process_iter():
        if proc.name == 'ser2sock':
            os.kill(proc.pid, signal.SIGHUP)

def save_certificate_index(path):
    path = os.path.join(path, 'certs', 'certindex')

    with open(path, 'w') as cert_index:
        for cert in Certificate.query.all():
            if cert.type != CA:
                revoked_time = ''
                if cert.revoked_on:
                    revoked_time = time.strftime('%y%m%d%H%M%SZ', cert.revoked_on.utctimetuple())

                subject = '/'.join(['='.join(t) for t in [()] + cert.certificate_obj.get_subject().get_components()])
                cert_index.write("\t".join([
                    CRL_CODE[cert.status],
                    cert.certificate_obj.get_notAfter()[2:],    # trim off the first two characters in the year.
                    revoked_time,
                    cert.serial_number.zfill(2),
                    'unknown',
                    subject
                ]) + "\n")

def save_revocation_list(path):
    path = os.path.join(path, 'ser2sock.crl')

    ca_cert = Certificate.query.filter_by(type=CA).first()

    with open(path, 'w') as crl_file:
        crl = crypto.CRL()

        for cert in Certificate.query.all():
            if cert.type != CA:
                if cert.status == REVOKED:
                    revoked = crypto.Revoked()

                    revoked.set_reason(None)
                    # NOTE: crypto.Revoked() expects YYYY instead of YY as needed by the cert index above.
                    revoked.set_rev_date(time.strftime('%Y%m%d%H%M%SZ', cert.revoked_on.utctimetuple()))
                    revoked.set_serial(cert.serial_number)

                    crl.add_revoked(revoked)

        crl_data = crl.export(ca_cert.certificate_obj, ca_cert.key_obj)
        crl_file.write(crl_data)