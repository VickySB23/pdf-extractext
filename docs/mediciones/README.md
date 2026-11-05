# Mediciones

- `00-registro.md`: registro cronológico de todos los experimentos y sus conclusiones.
- Los archivos se nombran `NN-etiqueta-...`, donde `NN` es un número de corrida. No coincide con el número de experimento del registro, que indica en cada caso qué archivos usa.
- `*-k6.json`: resumen de k6. `*-vegeta.txt` / `*.json`: reporte de Vegeta.
- `*-stats.txt`: consumo de CPU y memoria de los contenedores durante la prueba.
- Las corridas 20 a 23 son la medición final (Exp. 12 y 13); la 30 es el control posterior al refactor (Exp. 14).