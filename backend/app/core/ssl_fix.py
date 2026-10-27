"""
Self-healing SSL certificate guard.

Some sandboxes ship a `certifi` wheel whose cacert.pem payload is stripped
(the package imports fine, but certifi.where() points at a non-existent file).
curl_cffi (used by yfinance >= 0.2.54 for browser-impersonated TLS) reads
certifi.where() and libcurl then aborts every HTTPS request with
"curl: (77) error adding trust anchors".

This module repairs the bundle at import time by copying the OS trust store
onto the path certifi.where() expects. Import it BEFORE yfinance/curl_cffi.
"""
import logging
import os
import shutil

logger = logging.getLogger(__name__)
_REPAIR_DONE = False


def ensure_ssl_certs() -> bool:
    """Make sure certifi.where() exists; repair from the OS store if not."""
    global _REPAIR_DONE
    if _REPAIR_DONE:
        return True
    _REPAIR_DONE = True
    try:
        import certifi

        target = certifi.where()
        if os.path.exists(target) and os.path.getsize(target) > 10000:
            return True  # healthy

        candidates = [
            "/etc/ssl/certs/ca-certificates.crt",   # Debian/Ubuntu
            "/etc/pki/tls/certs/ca-bundle.crt",     # RHEL/Fedora
            "/etc/ssl/ca-bundle.pem",               # SUSE
        ]
        for src in candidates:
            if os.path.exists(src) and os.path.getsize(src) > 10000:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.copyfile(src, target)
                logger.warning(
                    "certifi bundle was missing/empty - repaired %s from %s (%d bytes)",
                    target, src, os.path.getsize(target),
                )
                return True

        # Last resort: point libcurl/curl_cffi at the OS store directly.
        if os.path.exists(candidates[0]):
            os.environ.setdefault("SSL_CERT_FILE", candidates[0])
            os.environ.setdefault("CURL_CA_BUNDLE", candidates[0])
        return False
    except Exception as exc:  # never crash the app over TLS hygiene
        logger.error("ssl_fix.ensure_ssl_certs failed: %s", exc)
        return False


ensure_ssl_certs()
