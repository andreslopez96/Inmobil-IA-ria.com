# Privacidad y publicación segura

La edición pública aplica minimización de datos: el repositorio contiene lógica, configuración, metadatos y ejemplos generados en tiempo de ejecución, pero ninguna fuente de datos.

## Contenido excluido

- Datasets y exportaciones tabulares, incluidos todos los ficheros CSV.
- Perfiles de clientes, emails reales y preferencias individuales.
- Credenciales, tokens, certificados y archivos `.env` locales.
- Modelos binarios, históricos de anuncios e informes generados.
- Notebooks archivados, outputs de celdas y rutas del equipo del autor.
- Recursos gráficos sin una licencia pública documentada.

## Barreras del repositorio

`.gitignore` bloquea esas categorías de forma global. `scripts/check_public_repo.py` revisa el árbol antes de publicar y la integración continua repite el control en GitHub. Las pruebas escriben sus artefactos únicamente en directorios temporales.

Antes de cada publicación:

```bash
python scripts/check_public_repo.py
git status --short
git diff --cached --name-only
```

Revisa manualmente el contenido staged. Una regla de ignore evita incorporaciones accidentales, pero no elimina un secreto que ya entró en el historial.

## Si una credencial se expone

1. Revócala o rótala inmediatamente en el proveedor.
2. Elimínala de todos los commits que vayan a conservarse.
3. Vuelve a ejecutar el control y revisa el historial completo.
4. No publiques el repositorio hasta confirmar la invalidación de la credencial.

Para un uso real deben definirse además base jurídica, control de acceso, retención y procedimientos de ejercicio de derechos. El pipeline local no sustituye esas obligaciones.
