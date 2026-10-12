# Laboratorio DevSecOps: Terraform + Ansible + Greenbone

Laboratorio práctico que integra la seguridad en el ciclo de vida de la infraestructura:
**crear → configurar → auditar → corregir**, todo como código versionado en Git.

**Resultado principal:** el entorno pasó de severidad **9.8 (Critical) a 0.0 (Log)** en tres
escaneos, y un pipeline automatizado aprueba la versión segura y rechaza la insegura.

| Herramienta | Rol | Pregunta que responde |
|---|---|---|
| Terraform | Crea la red, la imagen y los servidores | ¿Qué infraestructura existe? |
| Ansible | Configura y endurece los servidores; conecta Greenbone | ¿Cómo está configurado cada servidor? |
| Greenbone (OpenVAS 28.5) | Escanea y decide si el entorno es aceptable | ¿Qué tan seguro quedó? |

## Objetivo

Demostrar el enfoque **DevSecOps**: la seguridad deja de ser una revisión manual al final y pasa
a ser un paso automatizado del proceso. En este laboratorio:

- Un solo comando crea la infraestructura desde cero, siempre idéntica.
- La seguridad se **mide** con una herramienta independiente, no se supone.
- Cada corrección vive en el código y se aplica siempre a partir de ahí.
- Hay un antes y un después medible: **16 hallazgos → 6 → 0**.
- Un *security gate* detiene automáticamente una configuración insegura.

## Arquitectura

Tres contenedores Ubuntu 22.04 en la red `lab-net` (`172.30.0.0/24`) hacen de servidores.
Greenbone se conecta a esa red como segunda interfaz. El PC (Debian 13) es el nodo de control.

| Servidor | IP | Grupo | Estado final |
|---|---|---|---|
| web01 | 172.30.0.10 | web | Nginx con versión oculta |
| db01 | 172.30.0.11 | db | MariaDB, solo escucha en 127.0.0.1 |
| ftp01 | 172.30.0.12 | legacy | FTP y Telnet eliminados |
| Escáner | 172.30.0.128 | - | Contenedores ospd-openvas y openvasd de Greenbone |

El rango `172.30.0.10-127` es para IPs fijas y `172.30.0.128/25` para IPs automáticas,
así el escáner nunca choca con un servidor.

Estructura del repositorio:

- `Makefile`: une las tres herramientas.
- `terraform/`: `versions.tf`, `main.tf`, `outputs.tf`, `inventario.tftpl`, `target-image/Dockerfile`.
- `ansible/`: `ansible.cfg`, `inventario.ini` (generado), `site.yml`, `greenbone.yml`, `roles/` (common, web, db, legacy).
- `greenbone/`: `escanear.py` y `reportes/` (no versionado).
- `docs/`: documentación adicional.

Greenbone reutilizado: `/home/ronal/greenbone-community-container/compose.yaml`,
proyecto `greenbone-community-edition`, interfaz web en `http://127.0.0.1:9392`.

## Uso rápido

    read -rsp "Contraseña de Greenbone: " GVM_PASSWORD; echo; export GVM_PASSWORD
    make help          # lista de comandos
    make lab           # crea, configura, conecta y escanea
    make destruir      # desconecta Greenbone y destruye la infraestructura
    make reconstruir   # destruye y vuelve a crear todo desde cero

`make escanear` termina con código 1 (RECHAZADO) si algún hallazgo alcanza el umbral (`UMBRAL=7.0`).

## Fase 0: preparación del entorno

| Componente | Versión |
|---|---|
| Sistema operativo | Debian GNU/Linux 13 (trixie) |
| Docker / Compose | 29.9.0 / v5.5.0 |
| Terraform | 1.16.5 |
| Ansible | core 2.19.11 (paquete de Debian) |
| Python / Git | 3.13.5 / 2.47.3 |

Recursos: 7,6 GB de RAM (1,7 GB libres al inicio) y 15 GB de disco libres. Para escanear
se pausaron otros proyectos, subiendo la RAM disponible a 4,1 GB.

El `.gitignore` excluye: `terraform/.terraform/`, `*.tfstate`, `terraform/plan.tfplan`,
`ansible/.ssh/` y `greenbone/reportes/`.

## Fase 1: infraestructura con Terraform

Un `terraform apply` crea 8 recursos: llave SSH, archivo de la llave, red, imagen,
3 contenedores e inventario de Ansible.

- Imagen: Ubuntu 22.04 con `openssh-server` y `python3`; el proceso principal es `sshd -D`.
- Providers: `kreuzwerker/docker ~> 3.0`, `hashicorp/tls ~> 4.0`, `hashicorp/local ~> 2.5`.
- `locals` + `for_each`: un solo bloque crea los tres servidores con IP fija.
- `templatefile()` genera `ansible/inventario.ini` con los grupos `web`, `db`, `legacy` y `objetivos`.
- El state contiene la llave privada en texto plano: es un secreto y nunca va a Git.
- `terraform plan` detecta cambios manuales (drift), por ejemplo un `docker rm`.

## Fase 2: configuración insegura con Ansible

Se sembraron fallas a propósito para que Greenbone tuviera algo real que encontrar:

| Rol | Instalado | Fallas intencionales |
|---|---|---|
| common | Base | Root con contraseña `toor`; login de root y por contraseña en SSH |
| web | Nginx | Versión visible y carpeta `/backup/` listable |
| db | MariaDB | Escucha en `0.0.0.0` y `root@'%'` sin contraseña |
| legacy | vsftpd, inetd, telnetd | FTP anónimo y Telnet sin cifrado |

Conceptos: comandos ad-hoc, roles, handlers y `flush_handlers`, módulo `sysvinit` (sin systemd),
`kill -HUP 1` para recargar SSH, idempotencia manual con `register` + `when`, y ejecutar
dos veces exigiendo `changed=0`.

## Fase 3: conexión de Greenbone

El playbook `ansible/greenbone.yml` (sobre `localhost`, colección `community.docker`) conecta
`ospd-openvas` y `openvasd` a `lab-net` con `appends: true`. Un `assert` detiene todo si la
red no existe. El escáner recibió la IP 172.30.0.128 y se verificó la conectividad desde
dentro de su contenedor.

Dependencia descubierta: `terraform destroy` falla si el escáner sigue conectado a la red.
Se resolvió con `make destruir`, que primero lo desconecta.

## Fase 4: primer escaneo

Escaneo no autenticado (vista de un atacante) con *Full and fast* y *All IANA assigned TCP*.
Duración: 20 minutos. 16 hallazgos relevantes de 118 y 111 CVEs asociados.

| Severidad | Hallazgo | Origen |
|---|---|---|
| 9.8 | MySQL / MariaDB Default Credentials (db01) | Rol db |
| 9.8 | SSH Brute Force Logins With Default Credentials (x3) | Rol common |
| 6.4 | Anonymous FTP Login (ftp01) | Rol legacy |
| 4.8 | FTP y Telnet Unencrypted Cleartext Login (ftp01) | Rol legacy |
| 2.6 | Weak MAC Algorithm(s) Supported (SSH) | Valores por defecto de Ubuntu |
| 2.6 | TCP Timestamps Information Disclosure (x3) | Kernel |
| 2.1 | ICMP Timestamp Reply Information Disclosure (x3) | Kernel |

Lecturas: tres alertas críticas de SSH tenían una sola causa; QoD 95 % significa que Greenbone
realmente inició sesión; las vistas globales mezclan escaneos, hay que mirar el reporte de la tarea.

## Fase 5: hardening y remediación

**5. Ansible (`v2-seguro`):**

| Rol | Corrección |
|---|---|
| common | Actualizaciones, root sin contraseña, SSH solo con llave, MACs fuertes, validación con `sshd -t` |
| web | `server_tokens off` y carpeta `/backup/` eliminada |
| db | Escucha en `127.0.0.1` y root remoto eliminado |
| legacy | FTP y Telnet desinstalados |

Segundo escaneo: severidad máxima 2.6 (Low), 6 hallazgos, CVEs de 111 a 3.

**5b. Terraform (`v3-seguro-red`):** `sysctls = { "net.ipv4.tcp_timestamps" = "0" }`.
Forzó el reemplazo de los contenedores y Ansible los reconstruyó seguros desde el código.
Tercer escaneo: severidad máxima 2.1 (Low).

**5c. Riesgo aceptado:** el ICMP Timestamp Reply (2.1) requiere un firewall que los
contenedores no pueden gestionar. Se creó un override en Greenbone: nueva severidad Log,
hosts 172.30.0.10-12, vigente hasta el 7 de enero de 2027, con justificación escrita.
Con overrides aplicados, el reporte final muestra 0 de 83 resultados.

## Fase 6A: automatización y security gate

`greenbone/escanear.py` usa la API GMP de Greenbone mediante `gvm-script`: busca o crea su
target y su tarea, lanza el escaneo, espera, pide el reporte con overrides y compara la
severidad máxima con el umbral. Responde APROBADO (código 0) o RECHAZADO (código 1).

El `Makefile` encadena todo con `make lab`, se detiene ante cualquier error (`pipefail`),
aplica el plan exacto de Terraform (`plan -out`), toma las IPs del output de Terraform y
desconecta el escáner antes de destruir.

| Prueba del gate | Hallazgos | Severidad máxima | Resultado |
|---|---|---|---|
| Laboratorio seguro | 0 | 0.0 | APROBADO |
| Roles de `v1-inseguro` | 10 | 9.8 | RECHAZADO |

## Resultados

| Escaneo | Versión | Hallazgos | CVEs | Servicios expuestos | Severidad máxima |
|---|---|---|---|---|---|
| 1 | v1-inseguro | 16 | 111 | 5 | 9.8 Critical |
| 2 | v2-seguro | 6 | 3 | 2 | 2.6 Low |
| 3 | v3-seguro-red + override | 0 | 0 | 2 | 0.0 Log |

La duración del escaneo bajó de 20 a 11 minutos: menos superficie de ataque, menos que auditar.

## Problemas encontrados y soluciones

| Problema | Solución |
|---|---|
| `ftp01` con `changed=1` en cada ejecución: inetd moría sin servicios | Instalar `netbase` y declarar Telnet en `inetd.conf` |
| `pipx inject` falló | Ansible venía de apt: `sudo apt install python3-docker python3-passlib` |
| El escáner no tiene `bash` | Probar conectividad con `python3` |
| Results global mezclaba otras redes | Usar el reporte de la tarea |
| Override invisible en Tasks | Filtro `apply_overrides=1` |
| `Unsupported argument "sysctl"` | Corregir a `sysctls` |
| Poca RAM | Pausar otros proyectos antes de escanear |

## Lecciones aprendidas

1. Ejecutar dos veces y exigir `changed=0`: un cambio inesperado es una señal.
2. Cada hallazgo se corrige en su capa: Ansible, Terraform o una aceptación documentada.
3. Una corrección en un rol eliminó tres alertas críticas.
4. Los valores por defecto no son seguros.
5. Eliminar es la mejor corrección para un servicio innecesario.
6. Un gate solo es confiable después de verlo rechazar.
7. Los secretos nunca van al código.

## Pendientes

- [x] Agregar `docs/riesgos-aceptados.md`.
- [x] Prueba final: `make reconstruir; echo "Código de salida: $?"`.
- [x] Commit y etiqueta `v4-automatizado`.

## Fase 7: escaneos autenticados

Greenbone inicia sesión por SSH con el usuario `scanner` y revisa los paquetes por dentro.

- Llave del escáner generada con `ssh-keygen` fuera de Terraform: pertenece a Greenbone
  y debe sobrevivir a `make reconstruir`. No se versiona.
- Usuario `scanner` (rol `common`): sin contraseña, sin `sudo`, solo con llave.
- Credencial en Greenbone: `lab-scanner-ssh`. Comando: `make escanear-auth`.
- El script exige login SSH en todos los hosts: si falla, termina con ERROR (código 2).

| Escaneo autenticado | Paquetes | Hallazgos | Severidad máxima | Resultado |
|---|---|---|---|---|
| Primero | 529 | 3 | 6.5 Medium | APROBADO |
| Tras aceptar R-002 | 529 | 0 | 0.0 Log | APROBADO |

Lecciones:

- Ningún paquete vulnerable: `apt upgrade: dist` del hardening funciona.
- Downfall (GDS) era del host: los contenedores comparten su kernel. Sin parche del
  fabricante, se aceptó con condiciones (R-002 en `docs/riesgos-aceptados.md`).
- Un override debe tener Task y Result en Any para aplicar a escaneos futuros.
- La ausencia de hallazgos no prueba seguridad: hay que confirmar que el escaneo pudo medir.
