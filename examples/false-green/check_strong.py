"""The same checks plus the one case the claim is actually about."""
from refund import refund

assert refund(paid=100, requested=30) == 30
assert refund(paid=100, requested=100) == 100
assert refund(paid=100, requested=150) == 100, "refund exceeded the amount paid"
print("3 checks passed")
