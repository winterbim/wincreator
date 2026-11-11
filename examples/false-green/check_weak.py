"""A plausible, green test file that never exercises the claim it is used for."""
from refund import refund

assert refund(paid=100, requested=30) == 30
assert refund(paid=100, requested=100) == 100
print("2 checks passed")
