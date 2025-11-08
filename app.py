# ===============================================================
# app.py — Dovecot.io Flask Hub
# Version: 2025.11
# Description: Auto-language (IP-based) email diagnostics (Flask 3.x)
# License: MIT
# ===============================================================

from __future__ import annotations
import os, re, json, socket, ipaddress, logging, ssl
from datetime import datetime, date, timedelta
from pathlib import Path
from flask import (
    Flask, render_template, request, jsonify, Response, g, send_from_directory
)
import dns.resolver, dns.reversename

# ===============================================================
# Basic config
# ===============================================================
LANGS = {"zh", "en"}
DEFAULT_LANG = "en"
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")

# Global flag: whether client IP is in China (computed per request)
IS_CHINA_IP = False

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config.update(
    SECRET_KEY=SECRET_KEY,
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16MB upload limit
)

# ===============================================================
# Security headers
# ===============================================================
@app.after_request
def set_security_headers(response):
    """Add common security headers to every response."""
    response.headers.update({
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "SAMEORIGIN",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
    })
    # For strict CSP, uncomment and customize:
    # response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' 'unsafe-inline'"
    return response


def sanitize_path_param(value: str) -> str:
    """Whitelist only [a-zA-Z0-9_-] to avoid path injection."""
    return re.sub(r"[^a-zA-Z0-9_-]", "", value or "")

# ===============================================================
# China IP detector (optional; cached)
# ===============================================================
_ip_checker = None
_ip_cache: dict[str, tuple[bool, datetime]] = {}
_cache_expiry = timedelta(hours=1)

def init_ip_checker():
    """Initialize optional China-IP checker with a local GeoLite2 DB."""
    global _ip_checker
    try:
        from china_ip_checker import ChinaIPChecker
        _ip_checker = ChinaIPChecker(db_path="GeoLite2-Country.mmdb")
        logging.info("✅ ChinaIPChecker initialized")
    except Exception as e:
        logging.info(f"⚠️ ChinaIPChecker init failed: {e}")
        _ip_checker = None


def is_china_ip(ip_address: str) -> bool:
    """Return True if IP is in China (cached if possible)."""
    now = datetime.now()
    if ip_address in _ip_cache:
        result, ts = _ip_cache[ip_address]
        if now - ts < _cache_expiry:
            return result

    if _ip_checker:
        try:
            info = _ip_checker.check_single(ip_address)
            is_cn = info.get("is_china", False) and not info.get("error")
            _ip_cache[ip_address] = (is_cn, now)
            return is_cn
        except Exception:
            pass

    _ip_cache[ip_address] = (False, now)
    return False

# ===============================================================
# Request hooks: detect IP -> decide language -> maintenance gate
# ===============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    force=True
)

@app.before_request
def detect_ip_and_language():
    """
    Decide client language via IP:
    - China IP => zh
    - Otherwise => en
    """
    global IS_CHINA_IP
    xff = request.headers.get("X-Forwarded-For", "")
    remote = request.remote_addr or ""
    ips = [ip.strip() for ip in (xff + "," + remote).split(",") if ip.strip()]
    client_ip = ips[0] if ips else "unknown"

    IS_CHINA_IP =  is_china_ip(client_ip)
    g.client_ip, g.all_ips = client_ip, ips
    g.lang = "zh" if IS_CHINA_IP else "en"
    logging.info(f"[IP] {client_ip} | CN={IS_CHINA_IP} | LANG={g.lang}")



@app.after_request
def add_debug_ip_headers(response):
    """Expose client IP info in headers for debugging."""
    if hasattr(g, "client_ip"):
        response.headers["X-Client-IP"] = g.client_ip
    if hasattr(g, "all_ips"):
        response.headers["X-All-IPs"] = ",".join(g.all_ips)
    return response

# ===============================================================
# i18n helpers
# ===============================================================
def load_i18n(lang: str, name: str) -> dict:
    """
    Load i18n/<lang>/<name>.json.
    If missing, return {}.
    """
    path = Path(f"i18n/{lang}/{name}.json")
    if not path.exists():
        return {}
    data = json.load(path.open(encoding="utf-8"))
    # Simple runtime token replacement
    for k, v in list(data.items()):
        if isinstance(v, str):
            data[k] = v.replace("{year}", str(datetime.now().year))
    return data

@app.context_processor
def inject_template_helpers():
    """Expose load_i18n to Jinja templates if needed."""
    return dict(load_i18n=load_i18n)

def is_mobile_request() -> bool:
    """Rudimentary mobile detection by UA."""
    ua = (request.headers.get("User-Agent") or "").lower()
    return any(x in ua for x in ["iphone", "android", "ipad", "mobile"])

def current_lang() -> str:
    """Return language for this request."""
    return getattr(g, "lang", DEFAULT_LANG)

def common_context(lang: str | None = None) -> dict:
    """
    Common context for templates. Language auto-resolved if not provided.
    """
    lang = lang or current_lang()
    base = request.url_root.rstrip("/")
    return {
        "lang": lang,
        # We use root for both because we auto-detect language server-side
        "hreflang": {"zh": f"{base}/", "en": f"{base}/"},
        "common_text": load_i18n(lang, "common"),
        "now": datetime.now(),
    }

# ===============================================================
# API-side i18n for short phrases (fallback if you don't keep api.json)
# ===============================================================
def tr_api(lang: str, zh_text: str, en_text: str) -> str:
    """Simple inline translation helper for API messages."""
    return zh_text if lang == "zh" else en_text

# ===============================================================
# Pages & SEO (incl. favicon)
# ===============================================================
@app.route("/")
@app.route("/index.html")
def index():
    """Home: render with auto-detected language packs."""
    lang = current_lang()
    b = load_i18n(lang, "base")
    h = load_i18n(lang, "header")
    text = load_i18n(lang, "index")
    t = load_i18n(lang, "tools")
    common = load_i18n(lang, "common")
    return render_template(
        "index.html",
        text=text, t=t, h=h, b=b, common=common,
        **common_context(lang)
    )

@app.route("/terms")
def terms():
    lang = current_lang()
    b = load_i18n(lang, "base")
    h = load_i18n(lang, "header")
    l = load_i18n(lang, "legal")
    return render_template("terms.html", b=b, h=h, l=l, **common_context(lang))

@app.route("/privacy")
def privacy():
    lang = current_lang()
    b = load_i18n(lang, "base")
    h = load_i18n(lang, "header")
    l = load_i18n(lang, "legal")
    return render_template("privacy.html", b=b, h=h, l=l, **common_context(lang))

@app.get("/robots.txt")
def robots():
    """Robots.txt"""
    base = request.url_root.rstrip("/")
    body = f"User-agent: *\nAllow: /\nDisallow: /admin/\nSitemap: {base}/sitemap.xml\n"
    return Response(body, mimetype="text/plain; charset=utf-8")

@app.get("/sitemap.xml")
def sitemap():
    """Minimal sitemap (home only)."""
    base = request.url_root.rstrip("/")
    today = date.today().isoformat()
    xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    ]
    xml.append(f"<url><loc>{base}/</loc><lastmod>{today}</lastmod></url>")
    xml.append("</urlset>")
    return Response("\n".join(xml), mimetype="application/xml")

@app.route("/favicon.ico")
def favicon():
    """Serve favicon.ico to avoid 404s."""
    return send_from_directory(
        app.static_folder,
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon"
    )

@app.errorhandler(404)
def not_found(_):
    """Localized 404 page."""
    lang = current_lang()
    t = load_i18n(lang, "404")
    return render_template("404.html", t=t, lang=lang), 404

# ===============================================================
# Email diagnostics API (localized responses)
# ===============================================================
@app.post("/api/mx")
def api_mx():
    """DNS MX lookup."""
    lang = current_lang()
    domain = request.json.get("target", "").strip()
    if not domain:
        return jsonify({"ok": False, "error": tr_api(lang, "缺少目标域名", "Missing target domain")})
    try:
        answers = dns.resolver.resolve(domain, "MX")
        data = [{"host": str(r.exchange).rstrip("."), "pref": int(r.preference)} for r in answers]
        return jsonify({"ok": True, "data": data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.post("/api/spf")
def api_spf():
    """SPF record parsing."""
    lang = current_lang()
    domain = request.json.get("target", "").strip()
    if not domain:
        return jsonify({"ok": False, "error": tr_api(lang, "缺少目标域名", "Missing target domain")})
    try:
        txts = [str(r).strip('"') for r in dns.resolver.resolve(domain, "TXT")]
        spf = next((t for t in txts if t.startswith("v=spf1")), None)
        if not spf:
            raise Exception(tr_api(lang, "未找到 SPF 记录", "SPF record not found"))
        includes = spf.count("include:")
        policy = "-all" if "-all" in spf else "~all" if "~all" in spf else "?all"
        issues = [
            tr_api(lang, f"include 链 {includes}", f"include chain {includes}"),
            tr_api(lang, f"策略: {policy}", f"policy: {policy}")
        ]
        return jsonify({"ok": True, "data": spf, "issues": issues})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.post("/api/dkim")
def api_dkim():
    """Fetch DKIM public key(s) for given selector(s)."""
    lang = current_lang()
    data = request.get_json(force=True) or {}
    domain = (data.get("target") or "").strip()
    selectors = data.get("selectors", ["default"])
    if not domain:
        return jsonify({"ok": False, "error": tr_api(lang, "缺少目标域名", "Missing target domain")})
    results = []
    for s in selectors:
        name = f"{s}._domainkey.{domain}"
        try:
            txts = [str(r).strip('"') for r in dns.resolver.resolve(name, "TXT")]
            results.append({"selector": s, "pubkey": txts})
        except Exception as e:
            results.append({"selector": s, "error": str(e)})
    return jsonify({"ok": True, "data": results})

@app.post("/api/dmarc")
def api_dmarc():
    """DMARC record lookup."""
    lang = current_lang()
    domain = request.json.get("target", "").strip()
    if not domain:
        return jsonify({"ok": False, "error": tr_api(lang, "缺少目标域名", "Missing target domain")})
    try:
        name = f"_dmarc.{domain}"
        txts = [str(r).strip('"') for r in dns.resolver.resolve(name, "TXT")]
        return jsonify({"ok": True, "data": txts[0]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.post("/api/ports")
def api_ports():
    """Connectivity checks for common mail ports."""
    lang = current_lang()
    host = (request.json.get("host") or request.json.get("target") or "").strip()
    if not host:
        return jsonify({"ok": False, "error": tr_api(lang, "缺少目标主机或域名", "Missing target host or domain")})
    ports = [25, 465, 587, 143, 993, 110, 995]
    res = []
    for p in ports:
        try:
            with socket.create_connection((host, p), timeout=2):
                res.append({"service": f"{p}", "reachable": True})
        except Exception as e:
            res.append({"service": f"{p}", "reachable": False, "note": str(e)})
    return jsonify({"ok": True, "data": res})

@app.post("/api/tls")
def api_tls():
    """Basic TLS check on SMTPS(465)."""
    lang = current_lang()
    domain = request.json.get("target", "").strip()
    if not domain:
        return jsonify({"ok": False, "error": tr_api(lang, "缺少目标域名", "Missing target domain")})
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((domain, 465), timeout=3) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert() or {}
                # Extract CN from subject
                subject = cert.get("subject") or []
                cn = None
                for sub in subject:
                    for k, v in sub:
                        if k.lower() == "commonname":
                            cn = v
                            break
                    if cn:
                        break
                data = {
                    "starttls": False,
                    "minVersion": ssock.version(),
                    "certCN": cn or "(unknown)",
                    "weakCiphers": 0
                }
                return jsonify({"ok": True, "data": data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.post("/api/dnsbl")
def api_dnsbl():
    """Query a few DNSBLs for listing status."""
    lang = current_lang()
    domain = request.json.get("target", "").strip()
    if not domain:
        return jsonify({"ok": False, "error": tr_api(lang, "缺少目标域名", "Missing target domain")})
    try:
        ip = socket.gethostbyname(domain)
        rev_ip = ".".join(reversed(ip.split(".")))
        bls = [
            "zen.spamhaus.org",
            "bl.spamcop.net",
            "dnsbl.sorbs.net",
            "b.barracudacentral.org",
        ]
        listed = 0
        for bl in bls:
            try:
                dns.resolver.resolve(f"{rev_ip}.{bl}", "A")
                listed += 1
            except Exception:
                pass
        return jsonify({"ok": True, "data": {"checked": len(bls), "listed": listed}})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.post("/api/ptr")
def api_ptr():
    """Reverse PTR lookup for target's A record."""
    lang = current_lang()
    domain = request.json.get("target", "").strip()
    if not domain:
        return jsonify({"ok": False, "error": tr_api(lang, "缺少目标域名", "Missing target domain")})
    try:
        ip = socket.gethostbyname(domain)
        rev = dns.reversename.from_address(ip)
        ptr = str(dns.resolver.resolve(rev, "PTR")[0]).rstrip(".")
        return jsonify({"ok": True, "data": {"ip": ip, "ptr": ptr}})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

# ================== 启动 ==================
with app.app_context():
    init_ip_checker()

# ===============================================================
# Entrypoint
# ===============================================================
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8020")),
        debug=os.getenv("FLASK_DEBUG") == "1"
    )
