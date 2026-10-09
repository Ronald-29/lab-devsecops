FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      openssh-server python3 python3-apt sudo iproute2 \
 && mkdir -p /run/sshd /root/.ssh \
 && chmod 700 /root/.ssh \
 && rm -rf /var/lib/apt/lists/*

EXPOSE 22
CMD ["/usr/sbin/sshd", "-D", "-e"]
