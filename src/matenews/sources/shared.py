from __future__ import annotations

FAILED_TEXT = "No se puedo obtener texto."


def normalize_text_blocks(parts: list[str]) -> str:
    cleaned = [part.strip() for part in parts if part and part.strip()]
    if not cleaned:
        return FAILED_TEXT
    return "\n\n".join(cleaned)