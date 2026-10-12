# Escaneo automatizado del laboratorio usando la API de Greenbone (GMP).
# Se ejecuta con gvm-script, que entrega el objeto "gmp" ya autenticado.
# Uso: gvm-script ... socket escanear.py <umbral> <ip1,ip2,...> [credencial_ssh]
# Códigos de salida: 0 = APROBADO, 1 = RECHAZADO, 2 = ERROR (escaneo o login fallido)
import sys
import time

# Identificadores fijos que trae el feed de Greenbone
CONFIG_FULL_AND_FAST = "daba56c8-73ec-11df-a475-002264764cea"
ESCANER_OPENVAS = "08b69003-5fc2-4037-a479-93b440211c73"
PUERTOS_IANA_TCP = "33d0cd82-57c6-11e1-8ed1-406186ea4fc5"

# result_hosts_only=0: incluir todos los hosts, aunque no tengan resultados
FILTRO_REPORTE = ("apply_overrides=1 levels=chml min_qod=70 result_hosts_only=0 "
                  "rows=-1 sort-reverse=severity")


def primero(respuesta, ruta):
    valores = respuesta.xpath(ruta)
    return valores[0] if valores else None


def obtener_credencial(gmp, nombre):
    cred_id = primero(gmp.get_credentials(filter_string=f"name={nombre}"), "credential/@id")
    if not cred_id:
        print(f"ERROR: no existe la credencial '{nombre}' en Greenbone")
        sys.exit(2)
    print(f"Credencial SSH: {nombre}")
    return cred_id


def obtener_target(gmp, nombre, hosts, cred_id):
    existente = primero(gmp.get_targets(filter_string=f"name={nombre}"), "target/@id")
    if existente:
        print(f"Target existente: {nombre}")
        return existente
    opciones = {"name": nombre, "hosts": hosts, "port_list_id": PUERTOS_IANA_TCP}
    if cred_id:
        opciones["ssh_credential_id"] = cred_id
        opciones["ssh_credential_port"] = 22
    nuevo = gmp.create_target(**opciones)
    print(f"Target creado: {nombre} -> {', '.join(hosts)}")
    return nuevo.get("id")


def obtener_tarea(gmp, nombre, target_id):
    existente = primero(gmp.get_tasks(filter_string=f"name={nombre}"), "task/@id")
    if existente:
        print(f"Tarea existente: {nombre}")
        return existente
    nueva = gmp.create_task(name=nombre, config_id=CONFIG_FULL_AND_FAST,
                            target_id=target_id, scanner_id=ESCANER_OPENVAS)
    print(f"Tarea creada: {nombre}")
    return nueva.get("id")


def esperar(gmp, tarea_id):
    while True:
        tarea = gmp.get_task(tarea_id)
        estado = primero(tarea, "task/status/text()")
        progreso = primero(tarea, "task/progress/text()")
        print(f"  {time.strftime('%H:%M:%S')}  estado={estado}  progreso={progreso}%", flush=True)
        if estado in ("Done", "Stopped", "Interrupted"):
            return estado
        time.sleep(30)


def verificar_autenticacion(reporte, hosts_esperados):
    print("\nLogin SSH por host:")
    exitosos = set()
    for host in reporte.xpath("report/report/host"):
        ip = (host.findtext("ip") or "").strip()
        if host.xpath("detail[name='Auth-SSH-Success']"):
            exitosos.add(ip)
    for ip in hosts_esperados:
        print(f"  {ip:<13}  {'OK' if ip in exitosos else 'FALLÓ o sin datos'}")
    return [ip for ip in hosts_esperados if ip not in exitosos]


def main(gmp, args):
    if len(args.script) < 3:
        print("Uso: escanear.py <umbral> <ip1,ip2,...> [credencial_ssh]")
        sys.exit(2)
    umbral = float(args.script[1])
    hosts = [h for h in args.script[2].split(",") if h]
    credencial = args.script[3] if len(args.script) > 3 else None

    sufijo = "-auth" if credencial else ""
    cred_id = obtener_credencial(gmp, credencial) if credencial else None
    target_id = obtener_target(gmp, f"lab-pipeline-objetivos{sufijo}", hosts, cred_id)
    tarea_id = obtener_tarea(gmp, f"lab-pipeline-tarea{sufijo}", target_id)

    reporte_id = primero(gmp.start_task(tarea_id), "report_id/text()")
    print(f"Escaneo {'AUTENTICADO' if credencial else 'no autenticado'} iniciado (reporte {reporte_id})")
    estado = esperar(gmp, tarea_id)
    if estado != "Done":
        print(f"El escaneo terminó con estado {estado}")
        sys.exit(2)

    reporte = gmp.get_report(reporte_id, filter_string=FILTRO_REPORTE,
                             details=True, ignore_pagination=True)

    sin_login = verificar_autenticacion(reporte, hosts) if credencial else []

    hallazgos = []
    for r in reporte.xpath("report/report/results/result"):
        hallazgos.append((float(r.findtext("severity")),
                          r.xpath("host/text()")[0].strip(),
                          r.findtext("port"),
                          r.findtext("name")))
    hallazgos.sort(reverse=True)

    print("\nSEVERIDAD  HOST           PUERTO        HALLAZGO")
    for severidad, host, puerto, nombre in hallazgos:
        print(f"{severidad:>9.1f}  {host:<13}  {puerto:<12}  {nombre}")

    maxima = hallazgos[0][0] if hallazgos else 0.0
    print(f"\nHallazgos: {len(hallazgos)} | Severidad máxima: {maxima} | Umbral: {umbral}")

    if sin_login:
        print(f"RESULTADO: ERROR (sin login SSH en {', '.join(sin_login)}; el escaneo no es confiable)")
        sys.exit(2)
    if maxima >= umbral:
        print("RESULTADO: RECHAZADO")
        sys.exit(1)
    print("RESULTADO: APROBADO")


if __name__ == "__gmp__":
    main(gmp, args)
