import pytest
from unittest.mock import patch
from app.web.url_validator import validate_url
from app.web.exceptions import InvalidURLError, SSRFBlockedError

def test_url_validator_valid():
    # Test valid public URLs
    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(None, None, None, None, ("93.184.216.34", 80))]
        # Should not raise exception
        validate_url("https://example.com/some/path?param=value")
        validate_url("http://example.com")

def test_url_validator_unsupported_schemes():
    # Test invalid schemes
    with pytest.raises(InvalidURLError) as exc:
        validate_url("file:///etc/passwd")
    assert "Unsupported URL scheme" in str(exc.value)

    with pytest.raises(InvalidURLError):
        validate_url("ftp://example.com")

    with pytest.raises(InvalidURLError):
        validate_url("javascript:alert(1)")

def test_url_validator_credentials():
    # Test embedded credentials
    with pytest.raises(InvalidURLError) as exc:
        validate_url("https://user:pass@example.com")
    assert "credentials" in str(exc.value).lower()

def test_url_validator_localhost_and_loopback():
    # Test localhost string matching
    with pytest.raises(SSRFBlockedError):
        validate_url("http://localhost/path")

    with pytest.raises(SSRFBlockedError):
        validate_url("http://127.0.0.1/path")

    with pytest.raises(SSRFBlockedError):
        validate_url("http://[::1]/path")

def test_url_validator_decimal_ip():
    # Test integer/decimal IP representations (e.g. 2130706433 is 127.0.0.1)
    with pytest.raises(SSRFBlockedError):
        validate_url("http://2130706433")

def test_url_validator_private_ips():
    # Test private and link-local ranges
    with patch("socket.getaddrinfo") as mock_dns:
        # Private range 10.x
        mock_dns.return_value = [(None, None, None, None, ("10.0.0.1", 80))]
        with pytest.raises(SSRFBlockedError):
            validate_url("http://internal.service")

        # Private range 192.168.x
        mock_dns.return_value = [(None, None, None, None, ("192.168.1.100", 80))]
        with pytest.raises(SSRFBlockedError):
            validate_url("http://home.router")

        # Link local 169.254.x
        mock_dns.return_value = [(None, None, None, None, ("169.254.169.254", 80))]
        with pytest.raises(SSRFBlockedError):
            validate_url("http://aws-metadata")

        # Unspecified IP 0.0.0.0
        mock_dns.return_value = [(None, None, None, None, ("0.0.0.0", 80))]
        with pytest.raises(SSRFBlockedError):
            validate_url("http://unspecified")

def test_url_validator_dns_resolution_failure():
    with patch("socket.getaddrinfo", side_effect=Exception("DNS Error")):
        with pytest.raises(InvalidURLError) as exc:
            validate_url("http://nonexistent-domain.xyz")
        assert "DNS resolution failed" in str(exc.value)

def test_url_validator_mixed_dns_results():
    # Test when DNS returns mixed safe and unsafe IPs (e.g. one safe public, one loopback)
    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [
            (None, None, None, None, ("93.184.216.34", 80)),
            (None, None, None, None, ("127.0.0.1", 80))
        ]
        with pytest.raises(SSRFBlockedError):
            validate_url("http://mixed-ips.com")
