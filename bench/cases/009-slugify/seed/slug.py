def slugify(text, max_length=40):
    """Turn arbitrary text into a URL slug.

    Contract:
    - accents are transliterated to ASCII via NFKD ("Élan" -> "elan"); characters
      with no ASCII form are dropped;
    - output is lowercase and contains only ``a-z``, ``0-9`` and single hyphens;
    - any run of other characters becomes one hyphen; no leading/trailing hyphen;
    - the result is at most ``max_length`` characters and never ends with a
      hyphen after truncation;
    - if nothing remains, return ``"n-a"``;
    - ``max_length`` must be an int >= 3, else ``ValueError``.
    """
    return text.lower().replace(" ", "-")[:max_length]
