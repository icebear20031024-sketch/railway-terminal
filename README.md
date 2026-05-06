# railway-terminal

A minimal Railway browser terminal with `ttyd`, plus a VLESS WebSocket proxy on the same public HTTPS endpoint.

## What this is

This project runs three local services inside one container:

- `ttyd` on `127.0.0.1:7681`
- Xray VLESS WebSocket inbound on `127.0.0.1:10000`
- Nginx on public port `8080`

Railway exposes only one HTTP port, so Nginx routes traffic by path:

- `/` -> `ttyd`
- `/proxy` -> Xray VLESS WebSocket

## Runtime characteristics

- Base image: `ubuntu:24.04`
- Terminal server: `ttyd`
- Proxy core: Xray
- Public port: `8080`
- WebSocket proxy path: `/proxy`

## Files

- `Dockerfile` — builds the Ubuntu image with `ttyd`, Nginx, Supervisor, and Xray
- `nginx.conf` — routes `/` to ttyd and `/proxy` to Xray
- `xray.json` — VLESS WebSocket config
- `supervisord.conf` — starts all processes
- `.dockerignore` — keeps the build context small

## Local build

```bash
docker build -t railway-terminal .
docker run --rm -p 8080:8080 railway-terminal
```

Then open:

```text
http://localhost:8080
```

## Optional ttyd authentication

Set these Railway variables if you want the browser terminal protected:

```text
TTYD_USER=your-user
TTYD_PASS=your-password
```

If either variable is missing, ttyd starts without authentication.

## Railway deploy

1. Push this repository to GitHub.
2. Create or redeploy the Railway service from the repo.
3. Railway builds from `Dockerfile` automatically.
4. Open the generated public domain after deployment.

## VLESS subscription

Use this URL in clients that ask for a subscription link:

```text
https://railway-terminal-production.up.railway.app/sub
```

## VLESS WebSocket client parameters

```text
Protocol: VLESS
Address: railway-terminal-production.up.railway.app
Port: 443
UUID: b25ebeb5-185b-4666-b3bb-9a9b3cf0ad9a
Transport: WebSocket
WebSocket path: /proxy
TLS: enabled
SNI: railway-terminal-production.up.railway.app
```

URI for clients that support importing a single WebSocket node:

```text
vless://b25ebeb5-185b-4666-b3bb-9a9b3cf0ad9a@railway-terminal-production.up.railway.app:443?encryption=none&security=tls&type=ws&host=railway-terminal-production.up.railway.app&path=%2Fproxy#railway-terminal
```

## VLESS TCP Proxy client parameters

Create a Railway TCP Proxy with target port `10001`, then use the generated host and port.

Current TCP Proxy:

```text
Protocol: VLESS
Address: trolley.proxy.rlwy.net
Port: 52356
UUID: b25ebeb5-185b-4666-b3bb-9a9b3cf0ad9a
Transport: TCP
TLS: disabled
```

URI for clients that support importing a single TCP node:

```text
vless://b25ebeb5-185b-4666-b3bb-9a9b3cf0ad9a@trolley.proxy.rlwy.net:52356?encryption=none&security=none&type=tcp#railway-tcp
```

## Notes

- The shell is exposed through the web UI, so set `TTYD_USER` and `TTYD_PASS` before using it for anything sensitive.
- Container filesystem changes may be lost on redeploy or restart if no persistent volume is attached.
- Railway terminates public TLS, while the container listens on plain HTTP port `8080` internally.
