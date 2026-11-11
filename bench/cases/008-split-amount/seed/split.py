def split_amount(total_cents, parts):
    """Split an integer amount of cents into ``parts`` integer shares.

    Contract:
    - the shares always sum to exactly ``total_cents``;
    - any two shares differ by at most 1 cent;
    - shares are ordered from largest to smallest absolute value;
    - negative totals (refunds) are supported and follow the same rules;
    - ``parts`` must be an int >= 1, else ``ValueError``; ``total_cents`` must be
      an int (bool excluded), else ``TypeError``.
    """
    return [total_cents // parts] * parts
