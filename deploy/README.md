# Despliegue reproducible

Este directorio documenta el diseño de despliegue del proyecto privado. La imagen fija Python 3.11 y separa código, datos, modelos y artefactos mediante volúmenes. La edición pública no incluye el contenido necesario para poner el servicio en funcionamiento.

```bash
docker compose -f deploy/compose.yaml build
docker compose -f deploy/compose.yaml run --rm worker
```

El comando predeterminado ejecuta `doctor` y, en esta edición, informa de los componentes privados ausentes sin acceder a la red. La configuración se conserva para mostrar las fronteras del despliegue; no constituye un paquete operativo.
