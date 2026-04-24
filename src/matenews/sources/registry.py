from __future__ import annotations

from dataclasses import dataclass

from ..domain.models import SourceConfig
from .ambito import AmbitoSource
from .base import BaseSource
from .cohete import CoheteSource
from .eldia import ElDiaSource
from .elobservador import ElObservadorSource
from .infobae import InfobaeSource
from .lanacion import LanacionSource
from .letrap import LetraPSource
from .lpo import LPOSource
from .nodal import NodalSource
from .pagina12 import Pagina12Source
from .placeholder import PlaceholderSource
from .rt import RTSource


@dataclass(frozen=True, slots=True)
class SourceDefinition:
    config: SourceConfig
    implementation: type[BaseSource] | None = None

    @property
    def is_implemented(self) -> bool:
        return self.implementation is not None


SOURCE_DEFINITIONS = [
    SourceDefinition(
        SourceConfig(
            name="Infobae",
            slug="infobae",
            homepage_url="https://www.infobae.com/?noredirect",
            base_url="https://www.infobae.com",
        ),
        implementation=InfobaeSource,
    ),
    SourceDefinition(
        SourceConfig(
            name="Página 12",
            slug="pagina_12",
            homepage_url="https://www.pagina12.com.ar/?noredirect",
            base_url="https://www.pagina12.com.ar",
        ),
        implementation=Pagina12Source,
    ),
    SourceDefinition(
        SourceConfig(
            name="La Politica Online",
            slug="la_politica_online",
            homepage_url="https://www.lapoliticaonline.com",
            base_url="https://www.lapoliticaonline.com",
            limit=6,
        ),
        implementation=LPOSource,
    ),
    SourceDefinition(
        SourceConfig(
            name="La Nación",
            slug="la_nacion",
            homepage_url="https://www.lanacion.com.ar/",
            base_url="https://www.lanacion.com.ar",
            limit=10,
        ),
        implementation=LanacionSource,
    ),
    SourceDefinition(
        SourceConfig(
            name="Letra P",
            slug="letra_p",
            homepage_url="https://www.letrap.com.ar/",
            base_url="https://www.letrap.com.ar",
            limit=10,
        ),
        implementation=LetraPSource,
    ),
    SourceDefinition(
        SourceConfig(
            name="Nodal",
            slug="nodal",
            homepage_url="https://www.nodal.am/",
            base_url="https://www.nodal.am/",
        )
        ,
        implementation=NodalSource,
    ),
    SourceDefinition(
        SourceConfig(
            name="El Día",
            slug="el_dia",
            homepage_url="https://www.eldia.com/seccion/la-ciudad",
            base_url="https://www.eldia.com",
        ),
        implementation=ElDiaSource,
    ),
    SourceDefinition(
        SourceConfig(
            name="RT",
            slug="rt",
            homepage_url="https://actualidad.rt.com",
            base_url="https://actualidad.rt.com",
        )
        ,
        implementation=RTSource,
    ),
    SourceDefinition(
        SourceConfig(
            name="Financial Times",
            slug="financial_times",
            homepage_url="https://www.ft.com/",
            limit=8,
            enabled=False,
        )
    ),
    SourceDefinition(
        SourceConfig(
            name="El Cohete a la Luna",
            slug="el_cohete_a_la_luna",
            homepage_url="https://www.elcohetealaluna.com",
            base_url="https://www.elcohetealaluna.com",
            day_codes=("Do", "Lu"),
        )
        ,
        implementation=CoheteSource,
    ),
    SourceDefinition(
        SourceConfig(
            name="Ámbito",
            slug="ambito",
            homepage_url="https://r.jina.ai/https://www.ambito.com/economia",
        ),
        implementation=AmbitoSource,
    ),
    SourceDefinition(
        SourceConfig(
            name="El Observador",
            slug="el_observador",
            homepage_url="https://www.elobservador.com.uy/?nogeoredirect",
            base_url="https://www.elobservador.com.uy",
        ),
        implementation=ElObservadorSource,
    ),
]


def get_source_definitions() -> list[SourceDefinition]:
    return list(SOURCE_DEFINITIONS)


def get_source_instances(selected_slugs: set[str] | None = None) -> list[BaseSource]:
    instances: list[BaseSource] = []
    for definition in SOURCE_DEFINITIONS:
        if selected_slugs and definition.config.slug not in selected_slugs:
            continue
        implementation = definition.implementation or PlaceholderSource
        instances.append(implementation(definition.config))
    return instances