"""Direct private-LAN access policy. This app is not an internet-facing service."""

import hmac
import ipaddress
import os
import secrets
import time
from pathlib import Path
from urllib.parse import urlsplit
from flask import abort, jsonify, request, session


DEFAULT_ALLOWED_IPS = '10.104.13.115'  # Phone address from the supplied launcher.
MAX_REQUEST_BYTES = 4 * 1024 * 1024
WRITE_GET_ENDPOINTS = frozenset(('api_generate_bracket', 'api_trivia_round'))


def address(value):
    """Parse an IP address and normalise IPv4-mapped IPv6 values to their IPv4
    identity.
    """
    try:
        ip = ipaddress.ip_address(str(value))
        return ip.ipv4_mapped if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped else ip
    except ValueError:
        return None


def allowed_addresses(value):
    """Parse the configured exact-device IP allowlist and reject invalid or
    nonspecific addresses.
    """
    result = set()
    for item in value.split(','):
        if not item.strip():
            continue
        ip = address(item.strip())
        if ip is None or ip.is_unspecified or ip.is_multicast:
            raise RuntimeError('SONG_RANKER_ALLOWED_IPS must contain exact device IP addresses, separated by commas.')
        result.add(ip)
    return frozenset(result)


def load_secret(root, environment=None):
    """Persist a random signing key once; never fall back to a published secret."""
    environment = os.environ if environment is None else environment
    configured = environment.get('SONG_RANKER_SECRET')
    if configured is not None:
        if len(configured) < 32:
            raise RuntimeError('SONG_RANKER_SECRET must be at least 32 characters; use a randomly generated value.')
        return configured
    directory = Path(root) / 'instance'
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    path = directory / 'session_secret'
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, 'w', encoding='ascii') as stream:
            stream.write(secrets.token_hex(32))
            stream.flush()
            os.fsync(stream.fileno())
    # Another worker may have created the file but not finished its first write.
    for attempt in range(10):
        key = path.read_text(encoding='ascii').strip()
        if len(key) >= 32:
            path.chmod(0o600)
            return key
        if attempt < 9:
            time.sleep(.02)
    raise RuntimeError('instance/session_secret is incomplete. Restore its key or set SONG_RANKER_SECRET; do not use a shared default.')


def host_name(value):
    """Parse a Host value without credentials, paths or malformed ports and normalise
    its hostname.
    """
    try:
        parsed = urlsplit('http://' + value)
        if parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            return None
        parsed.port  # Reject malformed/out-of-range ports too.
        return parsed.hostname.lower().rstrip('.') if parsed.hostname else None
    except ValueError:
        return None


def valid_host(value, extra_names):
    """Accept configured names, localhost and concrete private/loopback IP hosts."""
    name = host_name(value)
    if not name:
        return False
    if name == 'localhost' or name in extra_names:
        return True
    ip = address(name)
    return bool(ip and (ip.is_private or ip.is_loopback) and not ip.is_unspecified and not ip.is_multicast)


def origin(value):
    """Normalise a valid HTTP(S) origin to its scheme, hostname and effective port."""
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
            return None
        return parsed.scheme, parsed.hostname.lower().rstrip('.'), parsed.port or (443 if parsed.scheme == 'https' else 80)
    except ValueError:
        return None


def configure_security(app, root, environment=None):
    """Install LAN host/origin/write guards, session settings and response
    protections on the app.
    """
    environment = os.environ if environment is None else environment
    allowed = allowed_addresses(environment.get('SONG_RANKER_ALLOWED_IPS', DEFAULT_ALLOWED_IPS))
    names = frozenset(name.strip().lower().rstrip('.') for name in environment.get('SONG_RANKER_HOSTNAMES', '').split(',') if name.strip())
    if any(host_name(name) != name or '*' in name or ':' in name for name in names):
        raise RuntimeError('SONG_RANKER_HOSTNAMES must contain exact hostnames, without schemes, wildcards or ports.')
    app.secret_key = load_secret(root, environment)
    app.config.update(DEBUG=False, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                      SESSION_COOKIE_SECURE=False, MAX_CONTENT_LENGTH=MAX_REQUEST_BYTES)
    app.extensions['song_ranker_security'] = dict(allowed=allowed, hostnames=names)

    def deny(message, status=403):
        """Return a JSON denial for API callers or the matching HTTP error for page
        requests.
        """
        if request.path.startswith('/api/'):
            return jsonify(message=message), status
        abort(status, description=message)

    @app.before_request
    def protect_lan_request():
        peer = address(request.remote_addr)
        local = bool(peer and peer.is_loopback)
        if not local and peer not in allowed:
            return deny('This device is not allowed. Check the phone IP in SONG_RANKER_ALLOWED_IPS.')
        if not valid_host(request.host, names):
            return deny('Use the computer\'s private LAN IP address, localhost, or a configured hostname.', 400)
        if not local and (request.path == '/dev' or request.path.startswith('/dev/')
                          or request.path == '/api/dev' or request.path.startswith('/api/dev/')):
            return deny('System Access is available only through localhost on the hosting computer.')
        # These routes include reads with side effects; ordinary page links stay usable.
        protected = request.path.startswith('/api/') or request.path.startswith('/dev/')
        if protected:
            source = request.headers.get('Origin')
            referer = request.headers.get('Referer')
            target = origin(request.host_url)
            if ((source is not None and origin(source) != target)
                    or (source is None and referer is not None and origin(referer) != target)
                    or request.headers.get('Sec-Fetch-Site', '').lower() in ('cross-site', 'same-site')):
                return deny('Requests must come from the Song Ranker page on this computer.')
        if request.endpoint in WRITE_GET_ENDPOINTS and request.method == 'HEAD':
            return deny('Use the app to create a round or bracket.', 405)
        writes = request.method not in ('GET', 'HEAD', 'OPTIONS') or (request.method == 'GET' and request.endpoint in WRITE_GET_ENDPOINTS)
        if request.path.startswith('/api/') and writes and request.mimetype != 'application/json':
            # JSON is not a CORS-safelisted content type. No CORS access is granted.
            return deny('This action requires a same-origin JSON request.')
        if request.endpoint == 'dev_login' and request.method == 'POST':
            expected = session.get('_login_csrf', '')
            supplied = request.form.get('csrf_token', '')
            if not expected or not hmac.compare_digest(str(expected).encode(), supplied.encode()):
                return deny('The sign-in form expired. Reload System Access and try again.')

    @app.context_processor
    def login_csrf_context():
        """Expose the session-backed login CSRF token helper to templates."""
        def csrf_token():
            """Create or reuse the current browser's login CSRF token."""
            if '_login_csrf' not in session:
                session['_login_csrf'] = secrets.token_urlsafe(32)
            return session['_login_csrf']
        return dict(csrf_token=csrf_token)

    @app.after_request
    def lan_response_headers(response):
        """Add browser isolation headers and prevent caching of Dev pages and
        responses.
        """
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Referrer-Policy', 'same-origin')
        if request.path.startswith('/dev/') or request.path.startswith('/api/dev/'):
            response.headers['Cache-Control'] = 'no-store'
        return response
