"""Money helpers. All arithmetic uses Decimal; totals are rounded half-up."""

from decimal import ROUND_HALF_UP, Decimal

CURRENCY_QUANTUM = Decimal("0.01")


def quantize_money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(CURRENCY_QUANTUM, rounding=ROUND_HALF_UP)


def compute_line_total(quantity: Decimal, unit_price: Decimal) -> Decimal:
    return quantize_money(Decimal(quantity) * Decimal(unit_price))
