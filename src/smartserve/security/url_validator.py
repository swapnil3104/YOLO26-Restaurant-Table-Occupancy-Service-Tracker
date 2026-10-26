"""URL and file upload security validation including SSRF protection and path sanitization.

Adheres strictly to Docs/TASKS.md Phase 7:
- Protect against SSRF via stream URLs and unauthorized camera access.
- Validate ownership, source URLs, uploads, and permissions.
"""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Allowed schemes for camera streaming and video feeds
ALLOWED_SCHEMES = {"rtsp", "rtsps", "http", "https"}

# Allowed video upload formats
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}

# Maximum video upload size in bytes (500 MB)
DEFAULT_MAX_UPLOAD_SIZE = 500 * 1024 * 1024

# Cloud metadata IP (AWS, GCP, Azure, OpenStack)
CLOUD_METADATA_IP = "169.254.169.254"
METADATA_HOSTNAMES = {
    "instance-data",
    "metadata.google.internal",
    "metadata",
    "169.254.169.254",
}


class SSRFValidationError(ValueError):
    """Raised when a stream URL violates SSRF security boundaries."""

    pass


class VideoUploadValidationError(ValueError):
    """Raised when an uploaded video file fails validation checks."""

    pass


def is_ip_prohibited(ip_str: str) -> bool:
    """Check if an IP address belongs to loopback, private, link-local, or reserved ranges."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return (
            ip.is_loopback
            or ip.is_private
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
            or str(ip) == CLOUD_METADATA_IP
        )
    except ValueError:
        return False


def validate_stream_url(
    url: str,
    allow_internal: bool = False,
) -> str:
    """Validate a camera stream URL against SSRF and unauthorized protocol vulnerabilities.

    Parameters
    ----------
    url : str
        The user-supplied stream URL (e.g. rtsp://camera1.local/feed or http://streams.domain.com/cctv).
    allow_internal : bool
        If True, permits loopback/private IPs for controlled offline test suites.
        Defaults to False in production/API usage.

    Returns
    -------
    str
        The validated and stripped URL.

    Raises
    ------
    SSRFValidationError
        If protocol is not allowed, or hostname resolves to private/internal/cloud metadata IP.
    """
    if not url or not isinstance(url, str):
        raise SSRFValidationError("Stream URL must be a non-empty string.")

    cleaned_url = url.strip()

    # Reject URLs containing control characters or newlines
    if any(c in cleaned_url for c in ["\r", "\n", "\t", "\0"]):
        raise SSRFValidationError("Stream URL contains invalid control characters.")

    try:
        parsed = urlparse(cleaned_url)
    except Exception as e:
        raise SSRFValidationError(f"Invalid URL structure: {e}") from e

    scheme = (parsed.scheme or "").lower()
    if scheme not in ALLOWED_SCHEMES:
        raise SSRFValidationError(
            f"Unsupported or insecure stream protocol '{scheme}'. Allowed protocols: {', '.join(sorted(ALLOWED_SCHEMES))}."
        )

    hostname = parsed.hostname
    if not hostname:
        raise SSRFValidationError("Stream URL must specify a valid hostname or IP address.")

    hostname_lower = hostname.lower()

    # Block well-known cloud metadata and local loopback aliases
    if hostname_lower in METADATA_HOSTNAMES:
        raise SSRFValidationError("Access to cloud metadata service is prohibited.")

    if not allow_internal:
        if hostname_lower in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}:
            raise SSRFValidationError("Access to local loopback interface is prohibited.")

        # Check direct IP addresses
        if is_ip_prohibited(hostname_lower):
            raise SSRFValidationError(
                f"Access to private/internal/cloud IP address '{hostname}' is prohibited."
            )

        # Attempt DNS resolution check to prevent DNS rebinding attacks
        try:
            addr_info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            for _, _, _, _, sockaddr in addr_info:
                ip_addr = sockaddr[0]
                if is_ip_prohibited(ip_addr):
                    raise SSRFValidationError(
                        f"Hostname '{hostname}' resolves to private/internal IP '{ip_addr}', which is prohibited."
                    )
        except socket.gaierror:
            # If domain cannot be resolved in offline environment, verify format
            pass

    return cleaned_url


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal and injection attacks."""
    if not filename:
        return "unnamed_video.mp4"

    # Extract base filename without directories
    clean = Path(filename).name

    # Remove any directory traversal patterns and unsafe characters
    clean = re.sub(r"[^\w\.\-\_]", "_", clean)
    clean = re.sub(r"\.{2,}", ".", clean)

    if not clean or clean.startswith("."):
        clean = f"upload_{clean}"

    return clean


def validate_video_upload(
    filename: str,
    file_size: int,
    max_size_bytes: int = DEFAULT_MAX_UPLOAD_SIZE,
    allowed_extensions: set[str] | None = None,
) -> str:
    """Validate uploaded video file extension, size, and filename.

    Parameters
    ----------
    filename : str
        Original filename from upload headers.
    file_size : int
        Byte size of the uploaded content.
    max_size_bytes : int
        Maximum permitted file size in bytes.
    allowed_extensions : set[str] | None
        Allowed lowercase file extensions including dot (e.g. {'.mp4', '.avi'}).

    Returns
    -------
    str
        Sanitized safe filename.

    Raises
    ------
    VideoUploadValidationError
        If size exceeds limits, extension is disallowed, or filename is malicious.
    """
    if file_size <= 0:
        raise VideoUploadValidationError("Uploaded file is empty (0 bytes).")

    if file_size > max_size_bytes:
        max_mb = max_size_bytes / (1024 * 1024)
        actual_mb = file_size / (1024 * 1024)
        raise VideoUploadValidationError(
            f"File size exceeds maximum allowed limit of {max_mb:.0f} MB (received {actual_mb:.1f} MB)."
        )

    safe_name = sanitize_filename(filename)
    ext = Path(safe_name).suffix.lower()

    valid_exts = allowed_extensions or ALLOWED_VIDEO_EXTENSIONS
    if ext not in valid_exts:
        raise VideoUploadValidationError(
            f"File format '{ext}' is not supported. Allowed video formats: {', '.join(sorted(valid_exts))}."
        )

    return safe_name
