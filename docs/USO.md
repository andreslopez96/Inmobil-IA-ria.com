# Recorrido del proyecto

Esta edición está preparada para leer y evaluar el trabajo, no para operar el sistema. Las rutas de datos, modelos y credenciales permanecen vacías o ignoradas de forma deliberada.

## 1. Orquestación

`src/inmobil_iaria/workflow.py` encadena las etapas y persiste únicamente el estado necesario para continuar tras la revisión humana.

- `collect_new_properties` recibe cualquier implementación de `PropertySource`.
- `run_core` se detiene en `awaiting_review` salvo aprobación explícita.
- `resume_pipeline` genera informes y solo notifica si recibe `send=True`.

## 2. Preparación y predicción

`preprocessing.py` convierte descripciones en variables numéricas y categóricas. `prediction.py` alinea exactamente las columnas esperadas por cada modelo, calcula sus estimaciones y las combina con pesos inversamente proporcionales al MSE.

Los metadatos de `models/` permiten inspeccionar los esquemas, pero los binarios entrenados no forman parte del repositorio.

## 3. Matching y decisión humana

`matching.py` filtra por precio, diferencia frente a la estimación, zona y preferencias. Las reglas están separadas en `config/matching_rules.yaml`.

Las oportunidades se escriben localmente para revisión. Ningún envío se produce durante esta primera parte del flujo.

## 4. Informes y notificaciones

`reporting.py` renderiza una plantilla LaTeX y reutiliza un informe cuando su huella no ha cambiado. `notifications.py` agrupa informes por destinatario y registra una clave solo después de la aceptación SMTP.

La plantilla pública usa únicamente texto, colores y formas; las imágenes del proyecto real no se distribuyen.

## 5. Interfaces

- `cli.py` expone cada etapa para diagnóstico y automatización controlada.
- `notebooks/operations/ACTUALIZADOR.ipynb` presenta el flujo al operador.
- `deploy/` documenta el aislamiento de código, datos, modelos y artefactos mediante volúmenes.

## 6. Verificación

`tests/unit/` comprueba transformaciones y reglas aisladas. `tests/integration/` fabrica datos y modelos mínimos dentro de un directorio temporal para verificar las conexiones entre módulos. Esos recursos desaparecen al terminar la prueba y nunca se versionan.

La CI repite las pruebas y el control de privacidad en cada cambio del repositorio.
