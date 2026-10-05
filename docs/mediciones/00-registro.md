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