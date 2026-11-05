# Mediciones

- `00-registro.md`: registro cronológico de todos los experimentos y sus conclusiones.
- Los archivos se nombran `NN-etiqueta-...`, donde `NN` es un número de corrida. No coincide con el número de experimento del registro, que indica en cada caso qué archivos usa.
- `*-k6.json`: resumen de k6. `*-vegeta.txt` / `*.json`: reporte de Vegeta.
- `*-stats.txt`: consumo de CPU y memoria de los contenedores durante la prueba.
- Las corridas 40 a 43 son la medición final (Exp. 19). Las 20 a 23 son la medición del commit `b3f9540` (Exp. 12 y 13) y la 30, el control posterior al refactor (Exp. 14).