"""Line pricing."""


def line_total(unit_cents, quantity):
    """Price of one order line in cents."""
    return unit_cents * quantity
