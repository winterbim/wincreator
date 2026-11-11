"""Line pricing, tax-aware revision."""


def line_total(unit_cents, quantity, tax_rate=0):
    """Price of one order line in cents, tax included (rounded half up)."""
    net = unit_cents * quantity
    return (net * (100 + tax_rate) + 50) // 100
