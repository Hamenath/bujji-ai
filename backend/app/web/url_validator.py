import socket
import ipaddress
import urllib.parse
from app.web.exceptions import InvalidURLError, SSRFBlockedError

def validate_url(url: str) -> None:
    """
    Validates a URL before fetching it.
    Protects against SSRF, dangerous schemes, embedded credentials, and loopback/private IPs.
    """
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception as e:
        raise InvalidURLError(f"Malformed URL: {e}", code="INVALID_URL")

    # 1. Scheme Check
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise InvalidURLError(f"Unsupported URL scheme: {scheme}", code="UNSUPPORTED_URL_SCHEME")

    # 2. Embedded Credentials Check
    if parsed.username or parsed.password or "@" in parsed.netloc:
        raise InvalidURLError("Embedded credentials are not allowed in URLs.", code="URL_CREDENTIALS_NOT_ALLOWED")

    # 3. Hostname Check
    hostname = parsed.hostname
    if not hostname:
        raise InvalidURLError("URL must contain a valid host.", code="INVALID_URL")

    hostname_lower = hostname.lower()
    
    # Direct loopback/localhost block (string matching check)
    if hostname_lower in ("localhost", "127.0.0.1", "[::1]"):
        raise SSRFBlockedError(f"Access to localhost/loopback is blocked: {hostname}", code="SSRF_BLOCKED")

    # Check for direct decimal/integer IP representation
    if hostname.isdigit():
        try:
            val = int(hostname)
            if 0 <= val <= 0xffffffff:
                ip = ipaddress.ip_address(val)
                ip_str = str(ip)
                if not _is_ip_safe(ip_str):
                    raise SSRFBlockedError(f"Access to private IP is blocked: {ip_str}", code="SSRF_BLOCKED")
        except ValueError:
            pass

    # 4. DNS Resolution & Resolved IP Validation
    try:
        addr_info = socket.getaddrinfo(hostname, None)
        ips = list(set(info[4][0] for info in addr_info))
    except Exception as e:
        raise InvalidURLError(f"DNS resolution failed for {hostname}: {e}", code="DNS_RESOLUTION_FAILED")

    if not ips:
        raise InvalidURLError(f"No IP addresses resolved for host: {hostname}", code="DNS_RESOLUTION_FAILED")

    # Validate all resolved IPs
    for ip_str in ips:
        # Strip scope ID from IPv6 addresses if present (e.g. fe80::1%lo0 -> fe80::1)
        clean_ip = str(ip_str).split("%")[0]
        if not _is_ip_safe(clean_ip):
            raise SSRFBlockedError(f"Access to unsafe resolved IP is blocked: {ip_str}", code="SSRF_BLOCKED")

def _is_ip_safe(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
        
        # Check standard properties
        if ip.is_loopback:
            return False
        if ip.is_private:
            return False
        if ip.is_link_local:
            return False
        if ip.is_multicast:
            return False
        if ip.is_unspecified:
            return False
        if ip.is_reserved:
            return False

        # Check IPv6-mapped IPv4 addresses
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            if not _is_ip_safe(str(ip.ipv4_mapped)):
                return False

        # Explicit metadata service check
        if str(ip) == "169.254.169.254":
            return False

        return True
    except ValueError:
        return False
