from __future__ import annotations

from ..domain.models import SourceBatch
from ..fetchers.http import HttpClient
from .base import BaseSource


class PlaceholderSource(BaseSource):
    def fetch(self, client: HttpClient) -> SourceBatch:
        return SourceBatch(source=self.config, articles=[])