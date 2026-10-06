# Registro de experimentos

## Exp. 1 - Baseline: pypdf, 1 réplica, sin backpressure (2026-10-05)
- Configuración: docker-compose.bench.yml, 1 réplica sin límites de recursos.
- k6 spike: 99 peticiones, 1,49 req/s, 86,9 % error, p50 50,5 s, p95 60 s.
- Vegeta 50 req/s (repetido con el servicio healthy): 0 % éxito
  (1.500 timeouts), p50 30 s.
- docker stats (durante k6): extraction-service 108 % CPU, 219 MiB;
  traefik 756 MiB.
- Observación: sin límite de concurrencia las extracciones se reparten la CPU
  y todas superan el timeout (colapso por saturación). Tras la prueba el
  servicio siguió procesando peticiones de clientes ya desconectados
  (118 % CPU).
- Hipótesis para el siguiente paso: la librería es el límite de capacidad
  (~0,5 req/s por núcleo); el backpressure evita el colapso pero no da
  capacidad.

  
## Exp. 2 - PyMuPDF, 1 réplica, sin backpressure (2026-10-05)
- Cambio respecto al Exp. 1: solo la librería (pypdf -> PyMuPDF con candado por proceso).
- Tiempo por PDF (curl, servicio descansado): 0,12 / 0,48 / 0,26 / 0,27 s
  (antes 1,5 / 4,0 / 1,7 / 4,3 s).
- k6 spike: 223 peticiones, 4,38 req/s, 13,5 % error (502), p50 18,1 s,
  p95 32,2 s, máx 37,6 s.
- Vegeta 50 req/s: 4,4 % éxito (66/1500), 1433 timeouts, p50 30 s.
- Observaciones: capacidad de una réplica ~4,4 req/s. Memoria posterior a la
  prueba: ~870 MiB (supera el límite de 512 MiB del TP): las peticiones en cola
  retienen su PDF completo. Trabajo desperdiciado en peticiones de clientes que
  ya hicieron timeout.
- Pendiente de diagnosticar: 502 de Traefik (30 en k6).
- Hipótesis siguiente: limitar la concurrencia ANTES de leer el cuerpo reduce la
  memoria y evita procesar peticiones muertas.

  
## Exp. 3 - PyMuPDF + backpressure, 1 réplica (MAX_CONCURRENT=1, cola 20 s)
- Cambio respecto al Exp. 2: semáforo adquirido antes de leer el cuerpo; 503 con
  Retry-After si la espera supera 20 s.
- k6 spike: 249 peticiones, 4,44 req/s, 13,3 % error (todo 503), p95 20,2 s,
  máx 20,75 s.
- Vegeta 50 req/s: 2,93 % éxito (44/1500), 1259 x 503, 197 con error de conexión
  (EOF/timeout), p50 20,5 s.
- Memoria del servicio: pico 352 MiB (k6) y 511,6 MiB (Vegeta). Antes ~870 MiB.
- Observación: durante el ataque de Vegeta el CPU del servicio cayó a 19-33 % en
  3 de 5 muestras con cientos de peticiones esperando (servicio ocioso).
- Hipótesis: con un solo permiso, el cuerpo del PDF se recibe dentro del lugar
  mientras el procesador espera. Se prueba con MAX_CONCURRENT=2 (Exp. 4).
- Traefik: sin logs; no aparecieron 502 en esta ronda.


## Exp. 4 - Igual que Exp. 3 pero MAX_CONCURRENT=2 (2026-10-05)
- Hipótesis a probar (del Exp. 3): con un solo permiso el cuerpo del PDF se
  recibe dentro del lugar mientras el procesador espera; con 2 permisos se
  solapan la recepción y la extracción.
- Configuración efectiva (log de arranque): MAX_CONCURRENT=2,
  QUEUE_TIMEOUT_SECONDS=20, RETRY_AFTER_SECONDS=1.
- k6 spike: 255 peticiones, 4,49 req/s, 7,1 % error, espera p95 ~20,3 s.
- Vegeta 50 req/s: 2,00 % éxito (30/1500), 1269 x 503, 201 errores de conexión
  (EOF/timeout), p50 21,1 s.
- Memoria del servicio: pico 698,7 MiB (Vegeta); ocioso quedó en ~270 MiB.
- Resultado: la hipótesis NO se confirma. El throughput no cambia (~4,4 req/s,
  limitado por CPU: ~100 % sostenido en k6) y la memoria sube. Se mantiene
  MAX_CONCURRENT=1.
- Notas: la mejora de errores en k6 (13 % -> 7 %) proviene de una sola corrida
  por configuración; no se la considera concluyente (repetir 3 veces para los
  números finales). Los ~200 errores EOF por corrida podrían deberse a que el
  servidor responde 503 y cierra la conexión mientras el cliente aún envía el
  cuerpo (hipótesis, no verificada).
- Pendiente: con el límite real de 512 MiB una réplica podría morir por falta
  de memoria (pico 511-699 MiB sin límite). Verificar OOMKilled en el Exp. 5.