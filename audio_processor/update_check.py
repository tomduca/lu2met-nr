"""App version and the check for newer releases on GitHub."""
import json
import logging
import os
import re
import ssl
import sys
import urllib.request
from pathlib import Path

RELEASES_URL = 'https://github.com/tomduca/lu2met-nr/releases'
# Returns the newest published release, excluding drafts and pre-releases.
LATEST_RELEASE_API = 'https://api.github.com/repos/tomduca/lu2met-nr/releases/latest'
VERSION_FILE = 'app_version.txt'
DEV_VERSION = 'dev'

_VERSION_RE = re.compile(r'^v?(\d+)\.(\d+)\.(\d+)(?:-(.+))?$')


def app_version():
    """Version of this build: written by the PyInstaller spec, 'dev' from source.

    LU2MET_NR_VERSION overrides it, which is useful to test the update banner.
    """
    override = os.environ.get('LU2MET_NR_VERSION')
    if override:
        return override
    base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    try:
        return (base / VERSION_FILE).read_text(encoding='utf-8').strip() or DEV_VERSION
    except OSError:
        return DEV_VERSION


def version_key(version):
    """Sortable key for 'v1.2.3' or '1.2.3-beta.1'; None if not a release version.

    A final release sorts after its pre-releases (1.2.0 > 1.2.0-beta.1).
    """
    match = _VERSION_RE.match(version.strip())
    if not match:
        return None
    major, minor, patch, suffix = match.groups()
    return (int(major), int(minor), int(patch), suffix is None)


def is_development(version):
    key = version_key(version)
    return key is None or version.startswith('0.0.0-dev')


def newer_release(current, latest_tag):
    """Return the latest tag if it is newer than the current version, else None."""
    if is_development(current):
        return None
    current_key = version_key(current)
    latest_key = version_key(latest_tag)
    if latest_key is None or latest_key <= current_key:
        return None
    return latest_tag


def release_from_json(data):
    """Extract (tag, url) from a GitHub 'latest release' API response."""
    tag = data.get('tag_name')
    if not tag or data.get('draft') or data.get('prerelease'):
        return None
    return tag, data.get('html_url') or f'{RELEASES_URL}/tag/{tag}'


def _ssl_context():
    # Packaged builds may not find the build machine's CA bundle; certifi ships its own.
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def fetch_latest_release(timeout=5.0):
    """Return (tag, url) of the latest stable release, or None on any failure."""
    request = urllib.request.Request(
        LATEST_RELEASE_API,
        headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'LU2MET-NR-Filter'},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=_ssl_context()) as response:
            return release_from_json(json.load(response))
    except (OSError, ValueError, AttributeError) as e:
        # No network, no release yet (404), rate limit, or unexpected content.
        logging.info(f'Update check: no release information ({e})')
        return None


def check_for_update(current):
    """Return (tag, url) when a newer stable release exists, else None."""
    if is_development(current):
        return None
    release = fetch_latest_release()
    if release and newer_release(current, release[0]):
        return release
    return None
