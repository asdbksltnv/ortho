"""Helpers that keep identifiers off shared screens, logs and outbound messages."""


def initials(full_name: str) -> str:
    """'Иванов Алишер Дилшодович' -> 'И. А. Д.' (first letters of up to three name parts)."""
    parts = [p for p in full_name.split() if p]
    return " ".join(f"{p[0].upper()}." for p in parts[:3])
