# ---------- Datos del laboratorio ----------
locals {
  servidores = {
    web01 = { ip = "172.30.0.10", grupo = "web" }
    db01  = { ip = "172.30.0.11", grupo = "db" }
    ftp01 = { ip = "172.30.0.12", grupo = "legacy" }
  }
}

# ---------- Llave SSH para Ansible ----------
resource "tls_private_key" "ansible" {
  algorithm = "ED25519"
}

resource "local_sensitive_file" "llave_ansible" {
  filename             = "${path.module}/../ansible/.ssh/lab_key"
  content              = tls_private_key.ansible.private_key_openssh
  file_permission      = "0600"
  directory_permission = "0700"
}

# ---------- Red del laboratorio ----------
resource "docker_network" "lab" {
  name   = "lab-net"
  driver = "bridge"

  ipam_config {
    subnet   = "172.30.0.0/24"
    gateway  = "172.30.0.1"
    ip_range = "172.30.0.128/25"
  }
}

# ---------- Imagen de los servidores ----------
resource "docker_image" "target" {
  name = "lab-target:latest"

  build {
    context = "${path.module}/target-image"
  }

  triggers = {
    dockerfile = filesha1("${path.module}/target-image/Dockerfile")
  }
}

# ---------- Los servidores ----------
resource "docker_container" "servidor" {
  for_each = local.servidores

  name     = each.key
  hostname = each.key
  image    = docker_image.target.image_id
  restart  = "unless-stopped"

  networks_advanced {
    name         = docker_network.lab.name
    ipv4_address = each.value.ip
  }

  upload {
    file    = "/root/.ssh/authorized_keys"
    content = tls_private_key.ansible.public_key_openssh
  }
}
