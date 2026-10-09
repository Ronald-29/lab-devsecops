# Escaneo automatizado del laboratorio usando la API de Greenbone (GMP).
# Se ejecuta con gvm-script, que entrega el objeto "gmp" ya autenticado.
# Uso: gvm-script ... socket escanear.py <umbral> <ip1,ip2,...>
import sys
import time

NOMBRE_TARGET = "lab-pipeline-objetivos"
NOMBRE_TAREA = "lab-pipeline-tarea"

# Identificadores fijos que trae el feed de Greenbone
CONFIG_FULL_AND_FAST = "daba56c8-73ec-11df-a475-002264764cea"
ESCANER_OPENVAS = "08b69003-5fc2-4037-a479-93b440211c73"
PUERTOS_IANA_TCP = "33d0cd82-57c6-11e1-8ed1-406186ea4fc5"

# Mismo filtro que usaste en la web: con overrides, sin "Log", confianza >= 70 %
FILTRO_REPORTE = "apply_overrides=1 levels=chml min_qod=70 rows=-1 sort-reverse=severity"


def primero(respuesta, ruta):
    valores = respuesta.xpath(ruta)
    return valores[0] if valores else None


def obtener_target(gmp, hosts):
    existente = primero(gmp.get_targets(filter_string=f"name={NOMBRE_TARGET}"), "target/@id")
    if existente:
        print(f"Target existente: {NOMBRE_TARGET}")
        return existente
    nuevo = gmp.create_target(name=NOMBRE_TARGET, hosts=hosts, port_list_id=PUERTOS_IANA_TCP)
    print(f"Target creado: {NOMBRE_TARGET} -> {', '.join(hosts)}")
    return nuevo.get("id")


def obtener_tarea(gmp, target_id):
    existente = primero(gmp.get_tasks(filter_string=f"name={NOMBRE_TAREA}"), "task/@id")
    if existente:
        print(f"Tarea existente: {NOMBRE_TAREA}")
        return existente
    nueva = gmp.create_task(name=NOMBRE_TAREA, config_id=CONFIG_FULL_AND_FAST,
                            target_id=target_id, scanner_id=ESCANER_OPENVAS)
    print(f"Tarea creada: {NOMBRE_TAREA}")
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


def main(gmp, args):
    if len(args.script) < 3:
        print("Uso: escanear.py <umbral> <ip1,ip2,...>")
        sys.exit(2)
    umbral = float(args.script[1])
    hosts = [h for h in args.script[2].split(",") if h]

    target_id = obtener_target(gmp, hosts)
    tarea_id = obtener_tarea(gmp, target_id)

    reporte_id = primero(gmp.start_task(tarea_id), "report_id/text()")
    print(f"Escaneo iniciado (reporte {reporte_id})")
    estado = esperar(gmp, tarea_id)
    if estado != "Done":
        print(f"El escaneo terminó con estado {estado}")
        sys.exit(2)

    reporte = gmp.get_report(reporte_id, filter_string=FILTRO_REPORTE,
                             details=True, ignore_pagination=True)
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
    if maxima >= umbral:
        print("RESULTADO: RECHAZADO")
        sys.exit(1)
    print("RESULTADO: APROBADO")


if __name__ == "__gmp__":
    main(gmp, args)
