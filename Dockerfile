FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /workspace

RUN apt-get update && apt-get install -y \
    bash \
    ca-certificates \
    curl \
    git \
    nano \
    nginx \
    supervisor \
    tmux \
    ttyd \
    unzip \
    vim \
    wget \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    arch="$(dpkg --print-architecture)"; \
    case "$arch" in \
      amd64) xray_arch="64" ;; \
      arm64) xray_arch="arm64-v8a" ;; \
      *) echo "unsupported architecture: $arch" >&2; exit 1 ;; \
    esac; \
    curl -fL "https://github.com/XTLS/Xray-core/releases/download/v1.8.24/Xray-linux-${xray_arch}.zip" -o /tmp/xray.zip; \
    unzip /tmp/xray.zip -d /tmp/xray; \
    install -m 755 /tmp/xray/xray /usr/local/bin/xray; \
    install -d /usr/local/share/xray /usr/local/etc/xray; \
    [ -f /tmp/xray/geoip.dat ] && install -m 644 /tmp/xray/geoip.dat /usr/local/share/xray/geoip.dat || true; \
    [ -f /tmp/xray/geosite.dat ] && install -m 644 /tmp/xray/geosite.dat /usr/local/share/xray/geosite.dat || true; \
    rm -rf /tmp/xray /tmp/xray.zip

COPY nginx.conf /etc/nginx/nginx.conf
COPY xray.json /usr/local/etc/xray/config.json
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

EXPOSE 8080

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
