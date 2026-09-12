# Seguridad del repositorio

Este repositorio solo debe contener código, configuración descriptiva y pruebas
con objetos sintéticos temporales. Nunca deben versionarse:

- `.env` ni sus variantes locales;
- contraseñas de aplicación, tokens o claves API;
- `data/raw/`, `data/processed/` o `data/private/`;
- modelos binarios `*.pkl`;
- revisiones, informes o correos reales;
- certificados o ficheros de credenciales.

Antes de cada publicación se debe revisar la lista exacta de archivos staged y
ejecutar una búsqueda de secretos. Si una credencial entra en un commit, borrarla
en otro commit no es suficiente: hay que revocarla o rotarla y eliminarla de todo
el historial que vaya a publicarse.

Las incidencias de seguridad no deben abrirse como issues públicos. Deben
comunicarse en privado al propietario del repositorio.
