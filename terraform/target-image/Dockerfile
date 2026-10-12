# checkov:skip=CKV_DOCKER_3: el proceso principal es sshd, que necesita root (riesgo R-003)
# checkov:skip=CKV_DOCKER_1: el puerto 22 es la interfaz de Ansible y del escaneo autenticado (riesgo R-003)
FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      openssh-server python3 python3-apt iproute2 \
 && mkdir -p /run/sshd /root/.ssh \
 && chmod 700 /root/.ssh \
 && rm -rf /var/lib/apt/lists/*

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD ["bash", "-c", "exec 3<>/dev/tcp/127.0.0.1/22"]

EXPOSE 22
CMD ["/usr/sbin/sshd", "-D", "-e"]
