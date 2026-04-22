from __future__ import annotations

from abc import ABC, abstractmethod

from ..domain.models import SourceBatch, SourceConfig
from ..fetchers.http import HttpClient


class BaseSource(ABC):
    def __init__(self, config: SourceConfig) -> None:
        self.config = config

    @abstractmethod
    def fetch(self, client: HttpClient) -> SourceBatch:
        raise NotImplementedError