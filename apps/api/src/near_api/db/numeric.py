"""Validate exact NUMERIC bounds before PostgreSQL can round fractional digits."""

from decimal import Decimal, InvalidOperation


def exact_numeric(value: str | Decimal, *, precision: int = 78, scale: int = 30) -> Decimal:
    if not 0 <= scale <= precision <= 78:
        raise ValueError("Unsupported NUMERIC precision/scale")
    if not isinstance(value, (str, Decimal)):
        raise ValueError("Amounts require a decimal string or Decimal, never float")
    try:
        amount = Decimal(value)
    except InvalidOperation:
        raise ValueError("Invalid decimal amount") from None
    if not amount.is_finite():
        raise ValueError("Amounts must be finite")
    exponent = amount.as_tuple().exponent
    if max(-exponent, 0) > scale:
        raise ValueError("Amount would lose fractional precision")
    if amount and max(amount.adjusted() + 1, 0) > precision - scale:
        raise ValueError("Amount exceeds NUMERIC integer capacity")
    return amount
