class RateError(Exception):
    """Raised when a rate cannot be obtained."""


def fetch_rate(currency, http_get):
    """Return the EUR rate of ``currency`` as a Decimal.

    ``http_get(url)`` returns ``(status_code, body_text)``.
    """
    raise NotImplementedError
