import os
import argparse

from .client import Client
from . import __version__ as sewer_version
from .config import ACME_DIRECTORY_URL_STAGING, ACME_DIRECTORY_URL_PRODUCTION
from .lib import create_logger


def main():
    "See docs/sewer-cli.md for docs & examples"

    parser = argparse.ArgumentParser(
        prog="sewer",
        description="Sewer is an ACME client for getting certificates from Let's Encrypt",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s {version}".format(version=sewer_version.__version__),
        help="The currently installed sewer version.",
    )
    parser.add_argument(
        "--account_key",
        type=argparse.FileType("r"),
        help="Filepath of existing ACME account key to use.  Default is to create one.",
    )
    parser.add_argument(
        "--certificate_key",
        type=argparse.FileType("r"),
        help="Filepath to existing certificate key to use.  Default is to create one.",
    )
    parser.add_argument(
        "--dns",
        required=True,
        choices=[
            "cloudflare",
            "aurora",
            "acmedns",
            "aliyun",
            "hurricane",
            "rackspace",
            "dnspod",
            "duckdns",
            "cloudns",
            "powerdns",
            "gandi",
        ],
        help="The name of the legacy dns provider to use.  (will be replaced by --provider in 0.9)",
    )
    parser.add_argument(
        "--domain",
        required=True,
        help="The DNS identity which will be the certificate's Common Name.  May be a wildcard.",
    )
    parser.add_argument(
        "--alt_domains",
        default=[],
        nargs="*",
        help="Optional alternate (SAN) identities to be added to the CN on this certificate.",
    )
    parser.add_argument(
        "--alias_domain", help="*** accepted but not implemented through drivers yet ***"
    )
    parser.add_argument(
        "--bundle_name",
        help="The basename for the output files.  Default is the CN given by --domain.",
    )
    parser.add_argument(
        "--endpoint",
        default="production",
        choices=["production", "staging"],
        help="Select between Let's Encrypt's endpoints.  Default is production.",
    )
    parser.add_argument("--email", help="Email to be used for registration of an ACME account.")
    parser.add_argument(
        "--action",
        choices=["run", "renew"],
        default="renew",
        help="The action that you want to perform. [Obsolescent?  Changes nothing but message.]",
    )
    parser.add_argument(
        "--out_dir",
        default=os.getcwd(),
        help="""The dir where the certificate and keys file will be stored.
            default:  The directory you run sewer command.
            eg: --out_dir /data/ssl/
            """,
    )
    parser.add_argument(
        "--loglevel",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="The log level to output log messages at. \
        eg: --loglevel DEBUG",
    )
    parser.add_argument(
        "--acme_timeout",
        type=int,
        default=7,
        help="The maximum time the client will wait for a network call (HTTPS request to ACME server) to complete.  Default is 7",
    )
    parser.add_argument(
        "--prop_delay",
        type=int,
        default=0,
        help="Add n second delay for propagation after setup before asking for validation checks",
    )

    args = parser.parse_args()

    dns_provider = args.dns
    domain = args.domain
    alt_domains = args.alt_domains
    action = args.action
    account_key = args.account_key
    certificate_key = args.certificate_key
    bundle_name = args.bundle_name
    endpoint = args.endpoint
    email = args.email
    loglevel = args.loglevel
    out_dir = args.out_dir

    provider_kwargs = {}

    # Make sure the output dir user specified is writable
    if not os.access(out_dir, os.W_OK):
        raise OSError("The dir '{0}' is not writable".format(out_dir))

    logger = create_logger(None, loglevel)

    if args.alias_domain:
        provider_kwargs["alias"] = args.alias_domain
        logger.warning(
            "--alias_domain is accepted but does not work with unmodified legacy dns providers."
        )
    if args.prop_delay > 0:
        provider_kwargs["prop_delay"] = args.prop_delay

    # if args.prop_delay:
    # ...

    if account_key:
        account_key = account_key.read()
    if certificate_key:
        certificate_key = certificate_key.read()
    if bundle_name:
        file_name = bundle_name
    else:
        file_name = "{0}".format(domain)
    if endpoint == "staging":
        ACME_DIRECTORY_URL = ACME_DIRECTORY_URL_STAGING
    else:
        ACME_DIRECTORY_URL = ACME_DIRECTORY_URL_PRODUCTION

    if dns_provider == "cloudflare":
        from .dns_providers.cloudflare import CloudFlareDns

        CLOUDFLARE_EMAIL = os.environ.get("CLOUDFLARE_EMAIL", None)
        CLOUDFLARE_API_KEY = os.environ.get("CLOUDFLARE_API_KEY", None)
        CLOUDFLARE_TOKEN = os.environ.get("CLOUDFLARE_TOKEN", None)

        if CLOUDFLARE_EMAIL and CLOUDFLARE_API_KEY and not CLOUDFLARE_TOKEN:
            dns_class = CloudFlareDns(
                CLOUDFLARE_EMAIL=CLOUDFLARE_EMAIL,
                CLOUDFLARE_API_KEY=CLOUDFLARE_API_KEY,
                **provider_kwargs,
            )
        elif CLOUDFLARE_TOKEN and not CLOUDFLARE_EMAIL and not CLOUDFLARE_API_KEY:
            dns_class = CloudFlareDns(CLOUDFLARE_TOKEN=CLOUDFLARE_TOKEN, **provider_kwargs)
        else:
            err = (
                "ERROR:: Please supply either CLOUDFLARE_EMAIL and CLOUDFLARE_API_KEY"
                "or CLOUDFLARE_TOKEN as environment variables."
            )
            logger.error(err)
            raise KeyError(err)

        logger.info("chosen_dns_provider. Using {0} as dns provider.".format(dns_provider))

    elif dns_provider == "aurora":
        from .dns_providers.auroradns import AuroraDns

        try:
            AURORA_API_KEY = os.environ["AURORA_API_KEY"]
            AURORA_SECRET_KEY = os.environ["AURORA_SECRET_KEY"]

            dns_class = AuroraDns(
                AURORA_API_KEY=AURORA_API_KEY,
                AURORA_SECRET_KEY=AURORA_SECRET_KEY,
                **provider_kwargs,
            )
            logger.info("chosen_dns_provider. Using {0} as dns provider.".format(dns_provider))
        except KeyError as e:
            logger.error("ERROR:: Please supply {0} as an environment variable.".format(str(e)))
            raise

    elif dns_provider == "acmedns":
        from .dns_providers.acmedns import AcmeDnsDns

        try:
            ACME_DNS_API_USER = os.environ["ACME_DNS_API_USER"]
            ACME_DNS_API_KEY = os.environ["ACME_DNS_API_KEY"]
            ACME_DNS_API_BASE_URL = os.environ["ACME_DNS_API_BASE_URL"]

            dns_class = AcmeDnsDns(
                ACME_DNS_API_USER=ACME_DNS_API_USER,
                ACME_DNS_API_KEY=ACME_DNS_API_KEY,
                ACME_DNS_API_BASE_URL=ACME_DNS_API_BASE_URL,
                **provider_kwargs,
            )
            logger.info("chosen_dns_provider. Using {0} as dns provider.".format(dns_provider))
        except KeyError as e:
            logger.error("ERROR:: Please supply {0} as an environment variable.".format(str(e)))
            raise

    elif dns_provider == "aliyun":
        from .dns_providers.aliyundns import AliyunDns

        try:
            aliyun_ak = os.environ["ALIYUN_AK_ID"]
            aliyun_secret = os.environ["ALIYUN_AK_SECRET"]
            aliyun_endpoint = os.environ.get("ALIYUN_ENDPOINT", "cn-beijing")
            dns_class = AliyunDns(aliyun_ak, aliyun_secret, aliyun_endpoint, **provider_kwargs)
            logger.info("chosen_dns_provider. Using {0} as dns provider.".format(dns_provider))
        except KeyError as e:
            logger.error("ERROR:: Please supply {0} as an environment variable.".format(str(e)))
            raise

    elif dns_provider == "hurricane":
        from .dns_providers.hurricane import HurricaneDns

        try:
            he_username = os.environ["HURRICANE_USERNAME"]
            he_password = os.environ["HURRICANE_PASSWORD"]
            dns_class = HurricaneDns(he_username, he_password, **provider_kwargs)
            logger.info("chosen_dns_provider. Using {0} as dns provider.".format(dns_provider))
        except KeyError as e:
            logger.error("ERROR:: Please supply {0} as an environment variable.".format(str(e)))
            raise

    elif dns_provider == "rackspace":
        from .dns_providers.rackspace import RackspaceDns

        try:
            RACKSPACE_USERNAME = os.environ["RACKSPACE_USERNAME"]
            RACKSPACE_API_KEY = os.environ["RACKSPACE_API_KEY"]
            dns_class = RackspaceDns(RACKSPACE_USERNAME, RACKSPACE_API_KEY, **provider_kwargs)
            logger.info("chosen_dns_prover. Using {0} as dns provider. ".format(dns_provider))
        except KeyError as e:
            logger.error("ERROR:: Please supply {0} as an environment variable.".format(str(e)))
            raise

    elif dns_provider == "dnspod":
        from .dns_providers.dnspod import DNSPodDns

        try:
            DNSPOD_ID = os.environ["DNSPOD_ID"]
            DNSPOD_API_KEY = os.environ["DNSPOD_API_KEY"]
            dns_class = DNSPodDns(DNSPOD_ID, DNSPOD_API_KEY, **provider_kwargs)
            logger.info("chosen_dns_prover. Using {0} as dns provider. ".format(dns_provider))
        except KeyError as e:
            logger.error("ERROR:: Please supply {0} as an environment variable.".format(str(e)))
            raise

    elif dns_provider == "duckdns":
        from .dns_providers.duckdns import DuckDNSDns

        try:
            duckdns_token = os.environ["DUCKDNS_TOKEN"]
            dns_class = DuckDNSDns(duckdns_token=duckdns_token, **provider_kwargs)
            logger.info("chosen_dns_provider. Using {0} as dns provider.".format(dns_provider))
        except KeyError as e:
            logger.error("ERROR:: Please supply {0} as an environment variable.".format(str(e)))
            raise

    elif dns_provider == "cloudns":
        from .dns_providers.cloudns import ClouDNSDns

        try:
            dns_class = ClouDNSDns(**provider_kwargs)
            logger.info("chosen_dns_provider. Using {0} as dns provider.".format(dns_provider))
        except KeyError as e:
            logger.error("ERROR:: Please supply {0} as an environment variable.".format(str(e)))
            raise

    elif dns_provider == "powerdns":
        from .dns_providers.powerdns import PowerDNSDns

        try:
            powerdns_api_key = os.environ["POWERDNS_API_KEY"]
            powerdns_api_url = os.environ["POWERDNS_API_URL"]
            dns_class = PowerDNSDns(powerdns_api_key, powerdns_api_url, **provider_kwargs)
            logger.info("chosen_dns_provider. Using {0} as dns provider.".format(dns_provider))
        except KeyError as e:
            logger.error("ERROR:: Please supply {0} as an environment variable.".format(str(e)))
            raise

    elif dns_provider == "gandi":
        from .dns_providers.gandi import GandiDns

        try:
            gandi_api_key = os.environ["GANDI_API_KEY"]
            dns_class = GandiDns(GANDI_API_KEY=gandi_api_key, **provider_kwargs)
            logger.info("chosen_dns_provider. Using {0} as dns provider.".format(dns_provider))
        except KeyError as e:
            logger.error("ERROR:: Please supply {0} as an environment variable.".format(str(e)))
            raise

    else:
        raise ValueError("The dns provider {0} is not recognised.".format(dns_provider))

    client = Client(
        provider=dns_class,
        domain_name=domain,
        domain_alt_names=alt_domains,
        contact_email=email,
        account_key=account_key,
        certificate_key=certificate_key,
        ACME_DIRECTORY_URL=ACME_DIRECTORY_URL,
        LOG_LEVEL=loglevel,
        ACME_REQUEST_TIMEOUT=args.acme_timeout,
    )
    certificate_key = client.certificate_key
    account_key = client.account_key

    # prepare file path
    account_key_file_path = os.path.join(out_dir, "{0}.account.key".format(file_name))
    crt_file_path = os.path.join(out_dir, "{0}.crt".format(file_name))
    crt_key_file_path = os.path.join(out_dir, "{0}.key".format(file_name))

    # write out account_key in out_dir directory
    with open(account_key_file_path, "w") as account_file:
        account_file.write(account_key)
    logger.info("account key succesfully written to {0}.".format(account_key_file_path))

    if action == "renew":
        message = "Certificate Succesfully renewed. The certificate, certificate key and account key have been saved in the current directory"
        certificate = client.renew()
    else:
        message = "Certificate Succesfully issued. The certificate, certificate key and account key have been saved in the current directory"
        certificate = client.cert()

    # write out certificate and certificate key in out_dir directory
    with open(crt_file_path, "w") as certificate_file:
        certificate_file.write(certificate)
    with open(crt_key_file_path, "w") as certificate_key_file:
        certificate_key_file.write(certificate_key)

    logger.info("certificate succesfully written to {0}.".format(crt_file_path))
    logger.info("certificate key succesfully written to {0}.".format(crt_key_file_path))

    logger.info("the_end. {0}".format(message))
