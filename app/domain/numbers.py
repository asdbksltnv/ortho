from decimal import Decimal, InvalidOperation


def format_number(value: float | int | str | None, separator: str = ",") -> str:
    """Digits only, no units; decimal separator configurable. 36.60 -> '36,6', 85.0 -> '85'."""
    if value is None or value == "":
        return ""
    try:
        number = Decimal(str(value)).normalize()
    except InvalidOperation:
        return ""
    text = format(number, "f")
    return text.replace(".", separator)


def bmi(weight_kg: float | None, height_cm: float | None) -> float | None:
    if not weight_kg or not height_cm or weight_kg <= 0 or height_cm <= 0:
        return None
    meters = height_cm / 100
    return weight_kg / (meters * meters)
