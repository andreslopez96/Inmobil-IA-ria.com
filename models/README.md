# Modelos

Los binarios `.pkl` no se versionan por privacidad del entrenamiento, propiedad de los datos y compatibilidad de licencia. Una instalación operativa necesita ficheros autorizados en:

```text
models/random_forest/model.pkl
models/bagging/model.pkl
models/gradient_boosting/model.pkl
```

El SVR histórico, inactivo en `config/model_registry.yaml`, usa además:

```text
models/svr/model.pkl
models/svr/scaler.pkl
```

Cada directorio contiene únicamente un manifiesto descriptivo. El esquema exacto de variables, las métricas, los binarios y los datos de entrenamiento se han retirado de esta edición. `notebooks/training/Modelos.ipynb` se conserva sin dataset ni outputs para mostrar el enfoque seguido, no para reconstruir los modelos privados.
