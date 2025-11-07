# Dovecot.io — Universal Mail Configuration & Deliverability Inspector

**Dovecot.io** is an open-source, IP-aware mail configuration and deliverability diagnostic platform built with **Flask 3.x**.  
It provides instant DNS, TLS, and reputation checks for any mail domain, automatically localized for global users (English/Chinese).

> ⚙️ This project is not affiliated with the Dovecot mail server project.

## 🌟 Features

- **Auto Language Detection** — detects Chinese IPs and switches between English/Chinese automatically.
- **Comprehensive Email Tests**
  - MX / SPF / DKIM / DMARC record validation
  - Port connectivity (SMTP, IMAP, POP3)
  - TLS / STARTTLS certificate checks
  - DNSBL (reputation blacklist) lookup
  - PTR reverse DNS analysis
- **Clean & Responsive UI** — modern design, mobile-friendly layout.
- **Static-frontend Compatible** — can serve via Nginx, GitHub Pages, or any CDN.
- **No database required** — fully stateless Flask app.

## 🧰 Tech Stack

| Layer | Technology |
|-------|-------------|
| Backend | Python 3.10+, Flask 3.x |
| DNS Queries | dnspython |
| Geolocation | china-ip-checker (GeoLite2) |
| Frontend | Vanilla JS + CSS (no framework) |
| Templates | Jinja2 |
| Deployment | Gunicorn + Nginx (optional) |

## 🚀 Quick Start

### 1. Clone repository
```bash
git clone https://github.com/reshub-cn/dovecot.io.git
cd dovecot.io
```

### 2. Install dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Run locally
```bash
python app.py
```
👉 `http://127.0.0.1:8020`

### 4. Deploy (optional)
```bash
gunicorn -w 2 -b 127.0.0.1:8020 app:app
```

## 🌐 API Endpoints

| Endpoint | Description |
|-----------|-------------|
| `POST /api/mx` | MX record lookup |
| `POST /api/spf` | SPF validation |
| `POST /api/dkim` | DKIM public key retrieval |
| `POST /api/dmarc` | DMARC policy query |
| `POST /api/ports` | Port connectivity test |
| `POST /api/tls` | TLS handshake & CN inspection |
| `POST /api/dnsbl` | DNSBL blacklist check |
| `POST /api/ptr` | PTR reverse DNS lookup |

All APIs return JSON:
```json
{ "ok": true, "data": {...}, "error": null }
```

## 🌏 Internationalization (i18n)

The project uses JSON-based translations under `i18n/<lang>/`.

## 🤝 Contributing

Contributions are welcome!  
Please fork the repository and open a pull request for improvements or new diagnostic tools.

## 📄 License

MIT License © 2025  
Created by reshub-cn
