# Inmobil-IA-ria

Portfolio técnico de un pipeline de análisis inmobiliario: desde la captación y normalización de anuncios hasta la valoración con varios modelos, el cruce con criterios de búsqueda y la generación de informes tras una revisión humana.

> **Edición de exposición, no operativa.** Este repositorio permite estudiar la arquitectura y el código, pero no ejecutar el servicio real. No contiene datasets, ficheros CSV, datos de clientes, credenciales, informes ni modelos entrenados.

## El problema abordado

El proyecto organiza un proceso que originalmente requería varios pasos manuales:

- detectar anuncios recientes y evitar reprocesar IDs conocidos;
- convertir texto inmobiliario en variables consistentes;
- alinear las variables con varios modelos de regresión;
- ponderar estimaciones según el error de cada modelo;
- aplicar reglas de oportunidad y preferencias privadas;
- exigir una selección humana antes de crear informes o notificar.

## Flujo de trabajo

```text
PropertySource
      |
      v
captura -> validación -> procesado -> predicción -> matching
                                                    |
                                                    v
                                           revisión humana
                                                    |
                                                    v
                                            informe -> email
```

Cada etapa tiene entradas, salidas y validaciones explícitas. La lógica reside en `src/inmobil_iaria/`; el notebook operativo y la CLI actúan únicamente como interfaces.

## Cómo recorrer el proyecto

1. Empieza por [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) para ver los contratos y decisiones técnicas.
2. Abre [notebooks/operations/ACTUALIZADOR.ipynb](notebooks/operations/ACTUALIZADOR.ipynb) para seguir la experiencia del operador. Está limpio de outputs y tiene los envíos desactivados.
3. Sigue la orquestación en `src/inmobil_iaria/workflow.py`.
4. Revisa `preprocessing.py`, `prediction.py` y `matching.py` para ver las etapas centrales.
5. Consulta `tests/` para ver los casos esperados, los límites y el flujo de integración aislado.

## Decisiones técnicas destacadas

- `PropertySource` desacopla el pipeline de la tecnología de captura.
- Los esquemas se validan al entrar en cada etapa y fallan de forma explícita.
- El registro de modelos separa rutas, columnas, métricas y activación del código.
- La revisión humana rompe la automatización antes de cualquier acción externa.
- Los informes son deterministas y los envíos mantienen claves de idempotencia.
- Rutas privadas, temporales y generadas están separadas desde la configuración central.

## Estructura

```text
config/                 reglas y registro de modelos
data/                   documentación; sin fuentes de datos
models/                 metadatos; sin binarios entrenados
assets/reports/         plantilla LaTeX pública
notebooks/operations/   panel del flujo, sin outputs
notebooks/training/     referencia del entrenamiento, sin dataset
src/inmobil_iaria/      aplicación y reglas de negocio
tests/                  contratos y pruebas con datos sintéticos temporales
deploy/                 diseño de despliegue reproducible
scripts/                control previo a publicación
docs/                   arquitectura, recorrido y privacidad
```

## Qué se ha retirado

- Todos los CSV y demás exportaciones tabulares.
- Clientes reales, direcciones de correo y preferencias individuales.
- `.env`, contraseñas, tokens, claves API y rutas locales.
- Modelos serializados y cualquier dato usado para entrenarlos.
- Informes, imágenes de anuncios y artefactos de ejecución.
- Notebooks históricos y recursos gráficos sin licencia documentada.
- El historial Git del proyecto privado.

Las pruebas de integración construyen objetos y archivos ficticios solo dentro de directorios temporales. Sirven para verificar la coherencia del código en CI, pero no reproducen las valoraciones ni habilitan el flujo productivo.

## Calidad y privacidad

GitHub Actions valida los tests y ejecuta `scripts/check_public_repo.py` en cada cambio. El control falla si detecta datasets, binarios, archivos de entorno, credenciales conocidas, emails no ficticios o rutas personales.

La metodología completa de publicación está en [docs/PRIVACIDAD.md](docs/PRIVACIDAD.md). La plantilla pública no reutiliza recursos gráficos privados; consulta [docs/ASSETS.md](docs/ASSETS.md).

## Limitaciones

El repositorio no incluye lo necesario para generar una valoración inmobiliaria real. Los resultados del proyecto son orientativos y no sustituyen una tasación ni asesoramiento profesional. Cualquier integración con una fuente externa debe respetar sus condiciones de servicio y la normativa aplicable.

El código se muestra exclusivamente como proyecto personal y no concede derechos de reutilización, modificación o distribución. Consulta [LICENSE](LICENSE).
