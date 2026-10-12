# Registro de riesgos aceptados

Cada riesgo aceptado tiene justificación, responsable y fecha de revisión.
En Greenbone se implementa como un override; este archivo es su respaldo versionado.

| ID | Hallazgo | Hosts | Severidad | Aceptado | Revisión |
|---|---|---|---|---|---|
| R-001 | ICMP Timestamp Reply Information Disclosure | 172.30.0.10-12 | 2.1 Low a Log | 2026-10-09 | 2027-01-07 |
| R-002 | Missing Linux Kernel mitigations for GDS (Downfall, INTEL-SA-00828) | Host anfitrión (visto en 172.30.0.10-12) | 6.5 Medium a Log | 2026-10-12 | 2027-01-10 |

## R-001: ICMP Timestamp Reply

- OID: 1.3.6.1.4.1.25623.1.0.103190
- Riesgo: el servidor responde a peticiones ICMP tipo 13 y revela su hora interna.
- Impacto: bajo; solo facilita ataques contra generadores aleatorios basados en tiempo.
- Motivo: los contenedores no pueden gestionar un firewall propio.
- Mitigación en producción: bloquear ICMP tipo 13 y 14 en el firewall del host o de la red.
- Implementación: override en Greenbone, nueva severidad Log, vigencia de 90 días.
- Responsable: Ronal

## R-002: Downfall (GDS) en el procesador del host

- Detectado por: escaneo autenticado (Fase 7). Aparece en los tres servidores porque
  los contenedores comparten el kernel del host; el hallazgo es del equipo anfitrión.
- Procesador: Intel Core i5-6500T (Skylake, familia 6, modelo 94).
- Estado: el host carga el microcódigo más reciente disponible (0x9e a 0xf0), pero esa
  versión no incluye mitigación de GDS. No existe parche que instalar.
- Riesgo: un proceso local podría leer datos de otros procesos a través de la CPU.
- Requisito del ataque: el atacante necesita ejecutar código en la misma máquina.
- Alternativa evaluada y descartada: arrancar con `gather_data_sampling=force`, que
  desactiva AVX; reduce el rendimiento y rompe software que exige AVX (MongoDB 8).
- Motivo de aceptación: equipo de laboratorio de un solo usuario, sin código de terceros.
- Condición: en producción o en hardware compartido NO se acepta; se exige CPU no vulnerable.
- Solución definitiva: renovar el hardware.
- Implementación: override en Greenbone (nueva severidad Log, vigencia de 90 días).
- Responsable: Ronal
