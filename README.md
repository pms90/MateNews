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

Primero instala el proyecto en tu entorno:

```bash
python -m pip install -e .
```

En los comandos siguientes se usa `python`; asegúrate de que esté disponible en tu PATH.

```bash
python -m matenews.cli list-sources
python -m matenews.cli build --output-dir site
python -m matenews.cli build --all-sources --output-dir site
python -m matenews.cli publish --source-dir site --target-dir docs
```

Si ya instalaste el paquete con `pip install -e .`, también puedes usar el comando corto `matenews` en lugar de `python -m matenews.cli`.

La primera forma de build respeta la agenda diaria de cada fuente. La segunda ignora la agenda y genera una version completa con todas las fuentes activas.

El build escribe:

- site/index.html
- site/prev/<fecha>.html
- site/<slug>/<fecha>/<n>.html para noticias con pagina local
- site/prev/<slug>/<fecha>/<n>.html para snapshots historicos compatibles con las rutas actuales

El publish:

- sincroniza el contenido generado en site/ hacia otra carpeta publicable, por defecto docs/
- crea un commit separado de publicacion
- hace push al remoto Git configurado, salvo que se use --no-push

La web publicada queda en:

https://pms90.github.io/MateNews/

Ejemplos:

```bash
python -m matenews.cli build --output-dir site
python -m matenews.cli build --all-sources --output-dir site
python -m matenews.cli publish --source-dir site --target-dir docs --no-push
python -m matenews.cli publish --source-dir site --target-dir docs --remote origin --branch main
```

