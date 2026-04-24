# MateNews

🔗 https://pms90.github.io/MateNews/

MateNews es un agregador estático de noticias implementado en Python que adquiere contenidos desde múltiples medios digitales, normaliza títulos, enlaces, autores y cuerpos de artículo, y genera un sitio HTML publicable en GitHub Pages con estructura de rutas determinística y snapshots históricos por fecha.

Desde el punto de vista técnico, el proyecto está organizado como un pipeline reproducible compuesto por adapters de fuente, un cliente HTTP común, un modelo de dominio explícito, una capa de render estático y una CLI operacional. Cada fuente implementa una interfaz homogénea de adquisición sobre `SourceConfig`, `Article` y `SourceBatch`; el pipeline resuelve agenda por día, reutilización de secciones cacheadas para fuentes no reacquiridas, construcción incremental de páginas de índice y páginas de noticia, y publicación desacoplada mediante sincronización del artefacto generado hacia la carpeta servida por GitHub Pages. El sistema prioriza compatibilidad de salida, aislamiento entre adquisición y publicación, y operación repetible desde terminal con comandos explícitos de build y publish.

## Estado actual

- El contrato de salida del sitio está implementado como código Python y genera artefactos estáticos compatibles con la publicación actual en GitHub Pages.
- La capa de render utiliza templates HTML preservados a partir del sitio publicado y mantiene la estructura pública de índices, páginas de noticia y snapshots históricos.
- La operación del sistema está expuesta mediante una CLI reproducible para inspección de fuentes, builds completos, builds selectivos por fuente y publicación desacoplada.
- Las fuentes actualmente implementadas son Infobae, Página 12, La Política Online, Letra P, Nodal, El Día, RT, El Cohete a la Luna, Ámbito y El Observador.
- El pipeline soporta reutilización de secciones cacheadas para evitar reacquisición innecesaria cuando una fuente no debe o no conviene volver a consultarse.
- Financial Times permanece deshabilitada por defecto porque el origen responde 403 tanto en acceso directo como a través del mirror textual utilizado para mitigación.

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

Si quieres actualizar solo una fuente y conservar en el index las demas secciones ya cacheadas, puedes usar `--sources`. Por ejemplo, este comando vuelve a adquirir solo Letra P y deja el resto del sitio con la informacion previamente generada:

```bash
python -m matenews.cli build --sources letra_p --output-dir site
```

Ese flujo sirve para evitar volver a consultar fuentes que ya fueron adquiridas recientemente. Despues de ese build selectivo, la publicacion se hace igual que siempre:

```bash
python -m matenews.cli publish --source-dir site --target-dir docs --remote origin --branch main
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
python -m matenews.cli build --output-dir site
python -m matenews.cli build --all-sources --output-dir site
python -m matenews.cli build --sources letra_p --output-dir site
python -m matenews.cli publish --source-dir site --target-dir docs --no-push
python -m matenews.cli publish --source-dir site --target-dir docs --remote origin --branch main
```

