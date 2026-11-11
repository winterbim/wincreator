"""Checkout totals."""
from shop.pricing_v2 import line_total


def order_total(lines, tax_rate=0):
    """Total in cents for ``lines`` of ``(unit_cents, quantity)``."""
    return sum(line_total(unit, quantity, tax_rate) for unit, quantity in lines)
