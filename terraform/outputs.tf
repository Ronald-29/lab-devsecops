resource "local_file" "inventario" {
  filename = "${path.module}/../ansible/inventario.ini"
  content = templatefile("${path.module}/inventario.tftpl", {
    servidores = local.servidores
    llave      = abspath(local_sensitive_file.llave_ansible.filename)
  })
}

output "servidores" {
  description = "IP de cada servidor del laboratorio"
  value       = { for nombre, s in local.servidores : nombre => s.ip }
}
