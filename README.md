# MateNews

Migracion inicial de MateNews_v3.ipynb a un proyecto Python estructurado.

## Estado actual

- El contrato de salida del sitio ya esta encapsulado en codigo Python.
- El render usa templates HTML derivados del sitio publicado actual.
- Hay una CLI inicial para listar fuentes y generar builds locales reproducibles.
- Ya estan migradas: Infobae, Pagina 12, La Politica Online, Nodal, El Dia, RT, El Cohete a la Luna, Ambito y El Observador.
- El pipeline ya reusa secciones cacheadas para fuentes fuera de agenda, replicando el comportamiento del notebook.
- Financial Times queda deshabilitado por defecto porque su homepage responde 403 tanto en acceso directo como via mirror textual.

## Instalacion

```bash
python -m pip install -e .
```

## Uso

```bash
matenews list-sources
matenews build --output-dir site
matenews publish --source-dir site --target-dir docs
```

El build escribe:

- site/index.html
- site/prev/<fecha>.html
- site/<slug>/<fecha>/<n>.html para noticias con pagina local
- site/prev/<slug>/<fecha>/<n>.html para snapshots historicos compatibles con las rutas actuales

El publish:

- sincroniza el contenido generado en site/ hacia otra carpeta publicable, por defecto docs/
- crea un commit separado de publicacion
- hace push al remoto Git configurado, salvo que se use --no-push

Ejemplos:

```bash
matenews build --output-dir site
matenews publish --source-dir site --target-dir docs --no-push
matenews publish --source-dir site --target-dir docs --remote origin --branch main
```

## Siguientes pasos

- Separar la publicacion a GitHub Pages del build local
- Implementar una estrategia estable para Financial Times o reemplazarlo por una fuente equivalente