"""Refund rule used by the false-green demo."""


def refund(paid, requested):
    """Return the amount to refund. A refund never exceeds what was paid."""
    return min(requested, paid)
