from decimal import Decimal

from invoice import invoice_total

assert invoice_total([("19.99", 3)]) == Decimal("59.97")
assert invoice_total([("100.00", 1)], discount_percent=10, tax_percent=20) == Decimal("108.00")
print("ok")
