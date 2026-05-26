from __future__ import annotations

from dataclasses import dataclass, field

import requests


TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"


@dataclass(slots=True)
class TranslationClient:
    target_language: str = "es"
    source_language: str = "auto"
    timeout_seconds: float = 15.0
    max_chunk_chars: int = 3500
    session: requests.Session = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.session = requests.Session()

    def translate(
        self,
        text: str,
        *,
        target_language: str | None = None,
        source_language: str | None = None,
    ) -> str:
        normalized_text = _normalize_text(text)
        if not normalized_text:
            return ""

        resolved_target = target_language or self.target_language
        resolved_source = source_language or self.source_language
        translated_chunks = [
            self._translate_chunk(chunk, target_language=resolved_target, source_language=resolved_source)
            for chunk in _chunk_text(normalized_text, self.max_chunk_chars)
        ]
        return "\n\n".join(chunk for chunk in translated_chunks if chunk.strip()) or normalized_text

    def translate_to_spanish(self, text: str) -> str:
        return self.translate(text, target_language="es")

    def _translate_chunk(self, chunk: str, *, target_language: str, source_language: str) -> str:
        try:
            response = self.session.get(
                TRANSLATE_URL,
                params={
                    "client": "gtx",
                    "sl": source_language,
                    "tl": target_language,
                    "dt": "t",
                    "q": chunk,
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            translated_text = "".join(
                segment[0]
                for segment in payload[0]
                if isinstance(segment, list) and segment and segment[0]
            )
            return translated_text.strip() or chunk
        except (requests.RequestException, ValueError, IndexError, TypeError):
            return chunk


def translate_text(
    text: str,
    *,
    target_language: str = "es",
    source_language: str = "auto",
    translator: TranslationClient | None = None,
) -> str:
    client = translator or TranslationClient(
        target_language=target_language,
        source_language=source_language,
    )
    return client.translate(text, target_language=target_language, source_language=source_language)


def translate_to_spanish(text: str, *, translator: TranslationClient | None = None) -> str:
    client = translator or TranslationClient(target_language="es")
    return client.translate_to_spanish(text)


def _normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def _chunk_text(text: str, max_chunk_chars: int) -> list[str]:
    paragraphs = [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]
    if not paragraphs:
        return [text]

    chunks: list[str] = []
    current_chunk = ""

    for paragraph in paragraphs:
        if len(paragraph) > max_chunk_chars:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""
            chunks.extend(_split_long_paragraph(paragraph, max_chunk_chars))
            continue

        candidate = paragraph if not current_chunk else f"{current_chunk}\n\n{paragraph}"
        if len(candidate) <= max_chunk_chars:
            current_chunk = candidate
            continue

        chunks.append(current_chunk)
        current_chunk = paragraph

    if current_chunk:
        chunks.append(current_chunk)
    return chunks


def _split_long_paragraph(paragraph: str, max_chunk_chars: int) -> list[str]:
    words = paragraph.split()
    if not words:
        return []

    chunks: list[str] = []
    current_chunk = ""

    for word in words:
        if len(word) > max_chunk_chars:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""
            chunks.extend(word[index : index + max_chunk_chars] for index in range(0, len(word), max_chunk_chars))
            continue

        candidate = word if not current_chunk else f"{current_chunk} {word}"
        if len(candidate) <= max_chunk_chars:
            current_chunk = candidate
            continue

        chunks.append(current_chunk)
        current_chunk = word

    if current_chunk:
        chunks.append(current_chunk)
    return chunks