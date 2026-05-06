FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /workspace

RUN apt-get update && apt-get install -y \
    bash \
    ca-certificates \
    curl \
    git \
    nano \
    tmux \
    ttyd \
    vim \
    wget \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

EXPOSE 8080

CMD ["sh", "-lc", "ttyd -W -p ${PORT:-8080} bash"]
