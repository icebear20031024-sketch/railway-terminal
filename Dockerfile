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

RUN bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

COPY nginx.conf /etc/nginx/nginx.conf
COPY xray.json /usr/local/etc/xray/config.json
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY sub.txt /usr/share/nginx/html/sub.txt

EXPOSE 8080

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
