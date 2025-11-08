// =============================
// main.js — Dovecot.io 工具逻辑（多语言 i18n 版）
// =============================

// ---------- 工具函数 ----------
function getTarget() {
  const v = document.getElementById("target").value.trim();
  if (!v) {
    showAlert(i18n.alert_no_domain, "warning");
    return null;
  }
  const ok = /^[A-Za-z0-9._-]+\.[A-Za-z]{2,}$/.test(v);
  if (!ok) {
    showAlert(i18n.alert_invalid_domain, "error");
    return null;
  }
  return v.toLowerCase();
}

// ---------- 实际后端接口 ----------
async function callAPI(path, payload) {
  const url = `/api/${path}`;
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data;
  } catch (e) {
    console.error(`[${path}] error:`, e);
    return { ok: false, error: e.message || i18n.unknown_error };
  }
}

// ---------- 渲染逻辑 ----------
function renderResult(elId, res, tool) {
  const el = document.getElementById(elId);
  el.textContent = "";

  if (!res || !res.ok) {
    el.textContent = i18n.check_failed + (res?.error || i18n.unknown_error);
    return;
  }

  let txt = "";

  switch (tool) {
    case "mx":
      txt = res.data.map(r => i18n.mx_line.replace("{pref}", r.pref).replace("{host}", r.host)).join("\n");
      break;
    case "spf":
      txt = `${res.data}\n${(res.issues || []).map(i => "• " + i).join("\n")}`;
      break;
    case "dkim":
      txt = res.data
        .map(r =>
          r.pubkey
            ? `• selector: ${r.selector}\n  key: ${r.pubkey.toString().slice(0, 40)}...`
            : `• selector: ${r.selector}\n  ❌ ${r.error || i18n.unknown_error}`
        )
        .join("\n\n");
      break;
    case "dmarc":
      txt = res.data;
      break;
    case "ports":
      txt = res.data
        .map(r =>
          `${r.service.padEnd(10)} ${
            r.reachable ? i18n.ports_reachable : i18n.ports_unreachable
          }${r.note ? " — " + r.note : ""}`
        )
        .join("\n");
      break;
    case "tls":
      txt = `STARTTLS: ${res.data.starttls ? "✅" : "❌"}\nTLS: ${
        res.data.minVersion
      }\nCN: ${res.data.certCN}\nWeak ciphers: ${res.data.weakCiphers}`;
      break;
    case "dnsbl":
      txt = `Checked ${res.data.checked} lists, listed: ${res.data.listed}`;
      break;
    case "ptr":
      txt = `IP: ${res.data.ip}\nPTR: ${res.data.ptr}`;
      break;
    default:
      txt = JSON.stringify(res, null, 2);
  }

  el.textContent = txt;
}

// ---------- 汇总 ----------
const summaryStore = {};

function updateSummary(tool, res) {
  summaryStore[tool] = res;
  const lines = [];

  if (summaryStore.mx) {
    const n = (summaryStore.mx.data || []).length;
    lines.push(i18n.summary_mx.replace("{count}", n).replace("{status}", n ? "✅" : "❌"));
  }
  if (summaryStore.spf) {
    const s = summaryStore.spf.data || "";
    lines.push(i18n.summary_spf.replace("{policy}", s.includes("-all") ? "Strict (-all) ✅" : "Recommend -all ⚠️"));
  }
  if (summaryStore.dkim) {
    const n = (summaryStore.dkim.data || []).length;
    lines.push(i18n.summary_dkim.replace("{count}", n));
  }
  if (summaryStore.dmarc) {
    const s = summaryStore.dmarc.data || "";
    const policy = /p=(reject|quarantine)/i.test(s) ? "Has policy ✅" : "Missing/Relaxed ⚠️";
    lines.push(i18n.summary_dmarc.replace("{policy}", policy));
  }
  if (summaryStore.ports) {
    const bad = (summaryStore.ports.data || []).filter(x => x.reachable === false);
    const badPorts = bad.map(x => x.service).join(", ");
    const text = bad.length ? `⚠️ ${bad.length} unreachable (${badPorts})` : "✅ All reachable";
    lines.push(i18n.summary_ports.replace("{text}", text));
  }
  if (summaryStore.tls) {
    const w = summaryStore.tls.data?.weakCiphers ?? 0;
    const text = w > 0 ? "Weak ciphers ⚠️" : "Good ✅";
    lines.push(i18n.summary_tls.replace("{text}", text));
  }
  if (summaryStore.dnsbl) {
    const l = summaryStore.dnsbl.data?.listed ?? 0;
    const text = l > 0 ? `❌ ${l} listed` : "✅ None";
    lines.push(i18n.summary_dnsbl.replace("{text}", text));
  }
  if (summaryStore.ptr) {
    const ptr = summaryStore.ptr.data?.ptr;
    const text = ptr ? ptr : "⚠️ Not resolved";
    lines.push(i18n.summary_ptr.replace("{text}", text));
  }

  document.getElementById("out-summary").textContent = lines.join("\n");
}

// ---------- 按钮事件 ----------
document.querySelectorAll("[data-tool]").forEach(btn => {
  btn.addEventListener("click", async () => {
    const tool = btn.dataset.tool;
    const target = getTarget();
    if (!target) return;
    btn.disabled = true;
    const key = "out-" + tool;
    const el = document.getElementById(key);
    el.textContent = i18n.checking;
    try {
      const payload = { target };
      if (tool === "dkim") {
        const raw = document.getElementById("dkimSelectors").value.trim();
        payload.selectors = (raw || "default")
          .split(",")
          .map(s => s.trim())
          .filter(Boolean);
      }
      if (tool === "ports") {
        const host = document.getElementById("hostOverride").value.trim();
        if (host) payload.host = host;
      }
      const res = await callAPI(tool, payload);
      renderResult(key, res, tool);
      updateSummary(tool, res);
    } catch (e) {
      el.textContent = i18n.error_prefix + (e.message || i18n.unknown_error);
    } finally {
      btn.disabled = false;
    }
  });
});

// ---------- 一键体检 ----------
document.getElementById("runAll")?.addEventListener("click", async () => {
  const target = getTarget();
  if (!target) return;
  const order = ["mx", "spf", "dkim", "dmarc", "ports", "tls", "dnsbl", "ptr"];
  for (const t of order) {
    const b = document.querySelector(`[data-tool="${t}"]`);
    b?.click();
    await new Promise(r => setTimeout(r, 150));
  }
});

// ---------- 清空 ----------
document.getElementById("clearAll")?.addEventListener("click", () => {
  ["mx", "spf", "dkim", "dmarc", "ports", "tls", "dnsbl", "ptr", "summary"].forEach(id => {
    document.getElementById("out-" + id).textContent = "";
  });
  document.getElementById("dkimSelectors").value = "";
  document.getElementById("hostOverride").value = "";
});

// ---------- 主题切换 ----------
(function () {
  const THEME_KEY = "theme-preference";
  const btn = document.getElementById("themeToggle");
  const html = document.documentElement;
  const metaTheme = document.querySelector('meta[name="theme-color"]');

  function getPref() {
    return localStorage.getItem(THEME_KEY);
  }
  function setPref(value) {
    localStorage.setItem(THEME_KEY, value);
  }
  function applyTheme(theme) {
    html.setAttribute("data-theme", theme);
    updateMetaThemeColor();
    updateButton(theme);
  }
  function updateMetaThemeColor() {
    if (!metaTheme) return;
    const bg = getComputedStyle(html).getPropertyValue("--bg").trim() || "#0ea5e9";
    metaTheme.setAttribute("content", bg);
  }
  function updateButton(theme) {
    const modeText = theme === "dark" ? i18n.theme_dark : i18n.theme_light;
    btn.title = i18n.theme_label.replace("{mode}", modeText);
    btn.setAttribute("aria-label", modeText);
    btn.textContent = theme === "dark" ? "☀️" : "🌙";
  }
  function detectSystemTheme() {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  function init() {
    let pref = getPref();
    if (!pref) {
      pref = detectSystemTheme();
      setPref(pref);
    }
    applyTheme(pref);
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", e => {
      const newTheme = e.matches ? "dark" : "light";
      setPref(newTheme);
      applyTheme(newTheme);
    });
    btn?.addEventListener("click", () => {
      const cur = getPref() === "dark" ? "light" : "dark";
      setPref(cur);
      applyTheme(cur);
    });
  }
  init();
})();

// ---------- 弹窗 ----------
function showAlert(message, type = "info") {
  document.querySelectorAll(".alert-popup").forEach(e => e.remove());
  const alert = document.createElement("div");
  alert.className = `alert-popup ${type}`;
  alert.innerHTML = message;
  document.body.appendChild(alert);
  setTimeout(() => alert.classList.add("show"), 10);
  setTimeout(() => {
    alert.classList.remove("show");
    setTimeout(() => alert.remove(), 300);
  }, 3000);
}
