#!/usr/bin/env python3
import argparse
import concurrent.futures
import http.client
import json
import socket
import ssl
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

DEFAULT_TARGETS = """railway-sg-main https://railway-terminal-production.up.railway.app/proxy
railway-us-a1cb https://railway-terminal-production-a1cb.up.railway.app/proxy
railway-us-9efc https://railway-terminal-production-9efc.up.railway.app/proxy
devoted-ws-2c73 https://devoted-optimism-production-2c73.up.railway.app/proxy
devoted-ws-7cd6 https://devoted-optimism-production-7cd6.up.railway.app/proxy
devoted-tcp trolley.proxy.rlwy.net:33016
""".strip()

INDEX_HTML = r"""
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Railway 批量测速面板</title>
  <style>
    :root { color-scheme: dark; }
    body { margin: 0; font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #0f172a; color: #e2e8f0; }
    main { max-width: 1280px; margin: 0 auto; padding: 24px; }
    h1 { margin: 0 0 8px; font-size: 24px; }
    p { color: #94a3b8; line-height: 1.6; }
    textarea { width: 100%; min-height: 210px; box-sizing: border-box; padding: 14px; border: 1px solid #334155; border-radius: 10px; background: #020617; color: #e2e8f0; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 14px; line-height: 1.5; }
    textarea.small { min-height: 92px; }
    .row { display: flex; flex-wrap: wrap; gap: 10px; margin: 14px 0; align-items: center; }
    button, input { border-radius: 9px; border: 1px solid #334155; background: #1e293b; color: #e2e8f0; padding: 10px 12px; font-size: 14px; }
    button { cursor: pointer; }
    button.primary { background: #2563eb; border-color: #3b82f6; }
    button:hover { filter: brightness(1.12); }
    label { color: #cbd5e1; display: inline-flex; align-items: center; gap: 8px; }
    table { width: 100%; border-collapse: collapse; margin-top: 18px; overflow: hidden; border-radius: 10px; font-size: 13px; }
    th, td { padding: 9px 10px; border-bottom: 1px solid #1e293b; text-align: left; vertical-align: top; white-space: nowrap; }
    th { position: sticky; top: 0; background: #111827; color: #cbd5e1; cursor: pointer; user-select: none; }
    tr.ok { background: rgba(22, 163, 74, 0.06); }
    tr.bad { background: rgba(220, 38, 38, 0.1); }
    tr.warn { background: rgba(234, 179, 8, 0.08); }
    code { color: #bfdbfe; }
    .muted { color: #94a3b8; }
    .pill { display: inline-block; padding: 2px 7px; border-radius: 999px; background: #334155; color: #cbd5e1; font-size: 12px; }
    .status { min-height: 20px; color: #93c5fd; }
    .table-wrap { overflow-x: auto; border: 1px solid #1e293b; border-radius: 10px; }
    .err { color: #fca5a5; max-width: 360px; white-space: normal; }
  </style>
</head>
<body>
<main>
  <h1>Railway 批量测速面板</h1>
  <p>局域网访问本机页面，批量粘贴域名、URL 或 TCP endpoint，一键测试 DNS、TCP、TLS、HTTP TTFB 和 WebSocket 101 握手。</p>
  <textarea id="targets" spellcheck="false" placeholder="每行一个目标，例如：name https://domain.up.railway.app/proxy 或 name host:port；裸 .up.railway.app 域名会自动按 /proxy 测"></textarea>
  <div class="row">
    <button class="primary" id="run">一键测速</button>
    <button id="sample">填入示例</button>
    <button id="fillProxy">裸域名补 /proxy</button>
    <button id="clear">清空结果</button>
    <label>超时秒数 <input id="timeout" type="number" min="2" max="30" value="8" style="width:70px"></label>
    <label>并发 <input id="workers" type="number" min="1" max="50" value="16" style="width:70px"></label>
  </div>
  <p class="muted">前置/CDN 矩阵：把 raw 域名、CF CNAME、Worker 域名粘进去，再生成多路径测试项。</p>
  <textarea id="fronts" class="small" spellcheck="false" placeholder="每行一个前置域名，例如：\ndevoted-optimism-production-7cd6.up.railway.app\ncf.example.com\nxxx.workers.dev"></textarea>
  <div class="row">
    <label>路径 <input id="paths" value="/proxy,/ws,/api/ws" style="width:220px"></label>
    <button id="matrix">生成前置/路径矩阵</button>
  </div>
  <div class="status" id="status"></div>
  <div class="table-wrap">
    <table id="results">
      <thead>
        <tr>
          <th data-key="name">名称</th>
          <th data-key="target">目标</th>
          <th data-key="kind">类型</th>
          <th data-key="ip">IP</th>
          <th data-key="dns_ms">DNS</th>
          <th data-key="tcp_ms">TCP</th>
          <th data-key="tls_ms">TLS</th>
          <th data-key="http_status">HTTP</th>
          <th data-key="ttfb_ms">TTFB</th>
          <th data-key="total_ms">总耗时</th>
          <th data-key="ws_101">WS 101</th>
          <th data-key="error">错误</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
  </div>
</main>
<script>
const sample = `__DEFAULT_TARGETS__`;
const textarea = document.getElementById('targets');
const tbody = document.querySelector('#results tbody');
const statusEl = document.getElementById('status');
let rows = [];
let sortKey = 'total_ms';
let sortAsc = true;

textarea.value = localStorage.getItem('speedtest_targets') || sample;

document.getElementById('sample').onclick = () => { textarea.value = sample; };
document.getElementById('fillProxy').onclick = fillProxyPaths;
document.getElementById('matrix').onclick = generateMatrix;
document.getElementById('clear').onclick = () => { rows = []; render(); statusEl.textContent = ''; };
document.getElementById('run').onclick = runTests;
document.querySelectorAll('th[data-key]').forEach(th => th.onclick = () => {
  const key = th.dataset.key;
  if (sortKey === key) sortAsc = !sortAsc; else { sortKey = key; sortAsc = true; }
  render();
});

function fmt(v) {
  if (v === null || v === undefined || v === '') return '—';
  if (typeof v === 'number') return Math.round(v) + 'ms';
  return String(v);
}
function cls(r) {
  if (r.error) return 'bad';
  if (r.kind === 'tcp' && r.tcp_open) return 'ok';
  if (r.ws_101 || (r.http_status >= 200 && r.http_status < 400)) return 'ok';
  return 'warn';
}
function render() {
  const data = [...rows].sort((a, b) => {
    const av = a[sortKey] ?? Number.POSITIVE_INFINITY;
    const bv = b[sortKey] ?? Number.POSITIVE_INFINITY;
    if (typeof av === 'number' && typeof bv === 'number') return sortAsc ? av - bv : bv - av;
    return sortAsc ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
  });
  tbody.innerHTML = data.map(r => `
    <tr class="${cls(r)}">
      <td>${escapeHtml(r.name || '')}</td>
      <td><code>${escapeHtml(r.target || '')}</code></td>
      <td><span class="pill">${escapeHtml(r.kind || '')}</span></td>
      <td>${escapeHtml((r.ips || []).join(', ') || r.ip || '')}</td>
      <td>${fmt(r.dns_ms)}</td>
      <td>${fmt(r.tcp_ms)}${r.tcp_open ? ' ✓' : ''}</td>
      <td>${fmt(r.tls_ms)}</td>
      <td>${r.http_status || '—'}</td>
      <td>${fmt(r.ttfb_ms)}</td>
      <td>${fmt(r.total_ms)}</td>
      <td>${r.ws_101 ? '✓' : '—'}</td>
      <td class="err">${escapeHtml(r.error || '')}</td>
    </tr>
  `).join('');
}
function escapeHtml(s) {
  return String(s).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
}
function hostFromLine(line) {
  const trimmed = line.trim();
  if (!trimmed || trimmed.startsWith('#')) return '';
  const parts = trimmed.includes(',') ? trimmed.split(',') : trimmed.split(/\s+/);
  const raw = parts.length > 1 ? parts[parts.length - 1].trim() : trimmed;
  try {
    return raw.includes('://') ? new URL(raw).hostname : raw.replace(/^\[|\]$/g, '').split('/')[0].split(':')[0];
  } catch (_) {
    return raw;
  }
}
function fillProxyPaths() {
  const lines = textarea.value.split('\n').map(line => {
    const host = hostFromLine(line);
    if (!host || !host.endsWith('.up.railway.app')) return line;
    const name = line.trim().split(/[\s,]+/)[0];
    return `${name} https://${host}/proxy`;
  });
  textarea.value = lines.join('\n');
}
function generateMatrix() {
  const paths = document.getElementById('paths').value.split(',').map(x => x.trim()).filter(Boolean);
  const hosts = document.getElementById('fronts').value.split('\n').map(hostFromLine).filter(Boolean);
  const lines = [];
  for (const host of hosts) {
    const short = host.replace(/\.up\.railway\.app$/, '').replace(/[^a-zA-Z0-9]+/g, '-').replace(/^-|-$/g, '');
    for (const path of paths) {
      const cleanPath = path.startsWith('/') ? path : `/${path}`;
      lines.push(`${short}${cleanPath.replace(/\//g, '-')} https://${host}${cleanPath}`);
    }
  }
  textarea.value = lines.join('\n');
}
async function runTests() {
  localStorage.setItem('speedtest_targets', textarea.value);
  rows = [];
  render();
  statusEl.textContent = '测速中...';
  const started = performance.now();
  try {
    const res = await fetch('/api/test', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        targets: textarea.value,
        timeout: Number(document.getElementById('timeout').value || 8),
        workers: Number(document.getElementById('workers').value || 16)
      })
    });
    if (!res.ok) throw new Error(await res.text());
    const payload = await res.json();
    rows = payload.results || [];
    render();
    statusEl.textContent = `完成：${rows.length} 个目标，用时 ${Math.round(performance.now() - started)}ms`;
  } catch (e) {
    statusEl.textContent = '失败：' + e.message;
  }
}
</script>
</body>
</html>
""".replace("__DEFAULT_TARGETS__", DEFAULT_TARGETS.replace("`", "\\`"))


def now_ms():
    return time.perf_counter() * 1000


def parse_line(line):
    line = line.strip()
    if not line or line.startswith('#'):
        return None
    if ',' in line:
        name, target = [part.strip() for part in line.split(',', 1)]
        return name or target, target
    parts = line.split()
    if len(parts) >= 2:
        return parts[0], parts[1]
    return line, line


def normalize_target(name, target):
    if '://' in target:
        parsed = urlparse(target)
        scheme = parsed.scheme or 'https'
        host = parsed.hostname or target
        port = parsed.port or (443 if scheme == 'https' else 80)
        path = parsed.path or '/'
        if parsed.query:
            path += '?' + parsed.query
        return {"name": name, "target": target, "scheme": scheme, "host": host, "port": port, "path": path}
    if ':' in target and target.rsplit(':', 1)[1].isdigit():
        host, port_text = target.rsplit(':', 1)
        return {"name": name, "target": target, "scheme": "tcp", "host": host.strip('[]'), "port": int(port_text), "path": None}
    path = "/proxy" if target.endswith(".up.railway.app") else "/"
    normalized = f"https://{target}{path}" if path == "/proxy" else target
    return {"name": name, "target": normalized, "scheme": "https", "host": target, "port": 443, "path": path}


def resolve_host(host, timeout):
    start = now_ms()
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        ips = []
        for info in infos:
            ip = info[4][0]
            if ip not in ips:
                ips.append(ip)
        return ips, now_ms() - start, None
    except Exception as exc:
        return [], now_ms() - start, str(exc)
    finally:
        socket.setdefaulttimeout(old_timeout)


def tcp_connect(host, port, timeout):
    start = now_ms()
    sock = socket.create_connection((host, port), timeout=timeout)
    return sock, now_ms() - start


def test_tcp(meta, timeout):
    result = base_result(meta, "tcp")
    started = now_ms()
    ips, dns_ms, dns_error = resolve_host(meta["host"], timeout)
    result.update({"ips": ips, "dns_ms": dns_ms})
    if dns_error:
        result["error"] = dns_error
        result["total_ms"] = now_ms() - started
        return result
    try:
        sock, tcp_ms = tcp_connect(meta["host"], meta["port"], timeout)
        sock.close()
        result.update({"tcp_ms": tcp_ms, "tcp_open": True})
    except Exception as exc:
        result["error"] = str(exc)
    result["total_ms"] = now_ms() - started
    return result


def test_http(meta, timeout):
    result = base_result(meta, "http")
    started = now_ms()
    ips, dns_ms, dns_error = resolve_host(meta["host"], timeout)
    result.update({"ips": ips, "dns_ms": dns_ms})
    if dns_error:
        result["error"] = dns_error
        result["total_ms"] = now_ms() - started
        return result
    sock = None
    try:
        sock, tcp_ms = tcp_connect(meta["host"], meta["port"], timeout)
        result["tcp_ms"] = tcp_ms
        if meta["scheme"] == "https":
            tls_start = now_ms()
            context = ssl.create_default_context()
            sock = context.wrap_socket(sock, server_hostname=meta["host"])
            result["tls_ms"] = now_ms() - tls_start
        conn_class = http.client.HTTPSConnection if meta["scheme"] == "https" else http.client.HTTPConnection
        conn = conn_class(meta["host"], meta["port"], timeout=timeout)
        conn.sock = sock
        request_start = now_ms()
        conn.request("GET", meta["path"] or "/", headers={"User-Agent": "lan-speedtest/1.0"})
        response = conn.getresponse()
        result["ttfb_ms"] = now_ms() - request_start
        result["http_status"] = response.status
        result["headers"] = {k.lower(): v for k, v in response.getheaders()}
        response.read(1024)
        conn.close()
        result["total_ms"] = now_ms() - started
    except Exception as exc:
        result["error"] = str(exc)
        result["total_ms"] = now_ms() - started
        try:
            if sock:
                sock.close()
        except Exception:
            pass
    return result


def test_ws(meta, timeout):
    result = base_result(meta, "ws")
    started = now_ms()
    ips, dns_ms, dns_error = resolve_host(meta["host"], timeout)
    result.update({"ips": ips, "dns_ms": dns_ms})
    if dns_error:
        result["error"] = dns_error
        result["total_ms"] = now_ms() - started
        return result
    sock = None
    try:
        sock, tcp_ms = tcp_connect(meta["host"], meta["port"], timeout)
        result["tcp_ms"] = tcp_ms
        if meta["scheme"] == "https":
            tls_start = now_ms()
            context = ssl.create_default_context()
            sock = context.wrap_socket(sock, server_hostname=meta["host"])
            result["tls_ms"] = now_ms() - tls_start
        key = "dGhlIHNhbXBsZSBub25jZQ=="
        req = (
            f"GET {meta['path'] or '/proxy'} HTTP/1.1\r\n"
            f"Host: {meta['host']}\r\n"
            "Connection: Upgrade\r\n"
            "Upgrade: websocket\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        request_start = now_ms()
        sock.settimeout(timeout)
        sock.sendall(req.encode())
        data = sock.recv(4096).decode(errors="replace")
        status_line = data.splitlines()[0] if data else ""
        result["ttfb_ms"] = now_ms() - request_start
        result["http_status"] = 101 if " 101 " in f" {status_line} " else None
        result["ws_101"] = result["http_status"] == 101
        result["ws_status"] = status_line
    except Exception as exc:
        result["error"] = str(exc)
    finally:
        try:
            if sock:
                sock.close()
        except Exception:
            pass
    result["total_ms"] = now_ms() - started
    return result


def base_result(meta, kind):
    return {
        "name": meta["name"],
        "target": meta["target"],
        "kind": kind,
        "host": meta["host"],
        "port": meta["port"],
        "ips": [],
        "dns_ms": None,
        "tcp_ms": None,
        "tls_ms": None,
        "http_status": None,
        "ttfb_ms": None,
        "total_ms": None,
        "tcp_open": False,
        "ws_101": False,
        "error": "",
    }


def test_one(line, timeout):
    parsed = parse_line(line)
    if not parsed:
        return None
    meta = normalize_target(*parsed)
    if meta["scheme"] == "tcp":
        return test_tcp(meta, timeout)
    if meta["path"] in ("/proxy", "/ws", "/api/ws") or meta["path"].endswith(("/proxy", "/ws", "/api/ws")):
        return test_ws(meta, timeout)
    return test_http(meta, timeout)


class Handler(BaseHTTPRequestHandler):
    def send_index(self, include_body=True):
        body = INDEX_HTML.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if include_body:
            self.wfile.write(body)

    def do_HEAD(self):
        if self.path not in ("/", "/index.html"):
            self.send_error(404)
            return
        self.send_index(include_body=False)

    def do_GET(self):
        if self.path not in ("/", "/index.html"):
            self.send_error(404)
            return
        self.send_index()

    def do_POST(self):
        if self.path != "/api/test":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            targets_text = str(payload.get("targets", ""))
            timeout = max(1, min(30, float(payload.get("timeout", 8))))
            workers = max(1, min(50, int(payload.get("workers", 16))))
            lines = [line for line in targets_text.splitlines() if parse_line(line)]
            if len(lines) > 200:
                raise ValueError("一次最多测试 200 个目标")
            results = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                future_map = {executor.submit(test_one, line, timeout): line for line in lines}
                for future in concurrent.futures.as_completed(future_map):
                    value = future.result()
                    if value:
                        results.append(value)
            body = json.dumps({"results": results}, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            body = str(exc).encode()
            self.send_response(400)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(f"{self.client_address[0]} - {fmt % args}")


def main():
    parser = argparse.ArgumentParser(description="LAN batch speedtest page")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=18080)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"listening on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
