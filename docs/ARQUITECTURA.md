# Arquitectura de Inmobil-IA-ria

`notebooks/operations/ACTUALIZADOR.ipynb` es un panel fino. La única implementación de reglas de negocio está en `src/inmobil_iaria/` y puede ejecutarse también desde la CLI o un worker.

Las rutas tabulares de esta documentación describen artefactos de ejecución. Ninguno de esos ficheros forma parte del repositorio público: se crean localmente bajo directorios ignorados.

## Flujo y contratos

```text
PropertySource
    │ list[RawProperty]
    ▼
captura ─► validación ─► procesado ─► predicción ─► matching
                                                       │
                                                       ▼
                                              revisión humana
                                                       │
                                                       ▼
                                                informe ─► email
```

| Etapa | Entrada | Salida |
|---|---|---|
| captura | fuente intercambiable + IDs conocidos | `data/raw/properties_latest.csv` |
| procesado | contrato `RawProperty` | `data/processed/properties.csv` deduplicado por `id` |
| predicción | procesado + registro + metadatos | `data/processed/predictions.csv` |
| matching | predicciones + clientes + reglas | `artifacts/review/opportunities.csv` |
| informes | filas aprobadas + plantilla | `artifacts/reports/<id>/source.tex` y `report.pdf` |
| avisos | PDFs agrupados por cliente | confirmación SMTP + clave de idempotencia |

Los contratos se validan en `domain/properties.py` y `domain/clients.py`. Una etapa no continúa silenciosamente si faltan columnas, los IDs son inválidos o falla un modelo.

## Fuentes

`PropertySource` expone un único método: `collect_new(known_ids)`. Sus implementaciones son:

- `IdealistaBrowserSource`: fuente operativa; recorre la búsqueda reciente hasta encontrar varios IDs conocidos consecutivos y después extrae los anuncios nuevos.
- `FixtureSource`: pruebas completas sin red.
- `IdealistaApiSource`: punto de extensión desactivado hasta disponer de acceso oficial.

La implementación está en `sources/idealista_browser.py`. `scraping.py` solo conserva un import de compatibilidad temporal para código antiguo.

## Configuración

- `config/model_registry.yaml` decide qué modelos están activos.
- Cada `models/<modelo>/metadata.json` conserva columnas, versión y métricas; los pesos derivan del MSE, no del código.
- `config/matching_rules.yaml` contiene zonas, tramos y valores admitidos en la revisión.
- `ProjectPaths` escribe en la estructura nueva y conserva fallback de lectura para una instalación aún no migrada.

Los ficheros `.yaml` usan sintaxis JSON, subconjunto válido de YAML, para poder leerlos estrictamente con la biblioteca estándar.

## Estado e idempotencia

`.runtime/latest_run.json` registra `run_id`, fuente, estado, IDs, contadores, informes y claves de notificaciones ya confirmadas. Los informes reutilizan el PDF si el hash de su fuente no cambió. Un email se marca como enviado únicamente después de que SMTP acepte `send_message`.

El CSV sigue siendo adecuado para un único operador local. Antes de un despliegue multiusuario deben trasladarse ejecuciones, clientes, oportunidades y claves de idempotencia a una base de datos transaccional.
