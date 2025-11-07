# Dovecot.io — 通用邮件配置与可达性检测平台

**Dovecot.io** 是一个基于 **Flask 3.x** 构建的开源邮件配置诊断平台，自动根据访问者 IP 选择语言（中 / 英），快速检测邮件系统的 DNS、TLS、安全性与信誉问题。

> ⚙️ 本项目与 Dovecot 邮件服务器无任何关联，仅为独立检测工具。

## 🌟 特性亮点

- **自动语言识别**：根据访问者 IP 智能切换中 / 英语言包。
- **全面检测能力**
  - MX / SPF / DKIM / DMARC 配置检测
  - SMTP / IMAP / POP3 端口连通性
  - TLS / STARTTLS 握手与证书检查
  - DNSBL 黑名单信誉检测
  - PTR 反向解析检查
- **现代化界面**：简洁优雅、移动端自适应。
- **无状态设计**：无需数据库即可运行。

## 🧰 技术栈

| 模块 | 技术 |
|------|------|
| 后端 | Python 3.10+，Flask 3.x |
| DNS 查询 | dnspython |
| IP 判断 | china-ip-checker (GeoLite2) |
| 前端 | 原生 JS + CSS |
| 模板 | Jinja2 |
| 部署 | Gunicorn + Nginx（可选） |

## 🚀 快速开始

### 1️⃣ 克隆项目
```bash
git clone https://github.com/reshub-cn/dovecot.io.git
cd dovecot.io
```

### 2️⃣ 安装依赖
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3️⃣ 启动项目
```bash
python app.py
```
访问地址：👉 `http://127.0.0.1:8020`

### 4️⃣ 生产部署
```bash
gunicorn -w 2 -b 127.0.0.1:8020 app:app
```

## 🌐 接口说明

| 接口 | 功能 |
|------|------|
| `POST /api/mx` | MX 记录检测 |
| `POST /api/spf` | SPF 检查 |
| `POST /api/dkim` | DKIM 公钥查询 |
| `POST /api/dmarc` | DMARC 策略检测 |
| `POST /api/ports` | 邮件端口可达测试 |
| `POST /api/tls` | TLS 检查 |
| `POST /api/dnsbl` | DNSBL 黑名单检测 |
| `POST /api/ptr` | PTR 反向解析检查 |

返回示例：
```json
{ "ok": true, "data": {...}, "error": null }
```

## 🌏 多语言支持

所有文字内容均来自 `i18n/` 目录的 JSON 文件。系统自动根据访问者 IP 判断显示语言。

## 🤝 贡献指南

欢迎提交 PR！可以贡献：
- 翻译优化
- 新检测模块（如 ARC、MTA-STS）
- UI 改进或国际化增强

## 📄 开源协议

MIT License © 2025  
Created by reshub-cn
