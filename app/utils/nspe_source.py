"""Whether the stored source of a case is a page on nspe.org.

The case view attributes the opinion text to the NSPE Board of Ethical Review,
and shows the NSPE reuse notice, only when the stored source of the case
(documents.source) is an http(s) URL whose host is nspe.org or a subdomain of
it. The host is parsed, so a URL that merely contains "nspe.org" in its path or
query does not qualify.
"""
from typing import Optional
from urllib.parse import urlparse


def nspe_source_url(source) -> Optional[str]:
    """The source URL when its host is nspe.org or a subdomain of it, else None."""
    if not source:
        return None
    url = str(source).strip()
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or '').lower()
    except ValueError:
        return None
    if parsed.scheme in ('http', 'https') and (host == 'nspe.org' or host.endswith('.nspe.org')):
        return url
    return None
