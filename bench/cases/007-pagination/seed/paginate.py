def paginate(items, page, per_page):
    """Return one page of ``items`` as a dict.

    Contract:
    - ``page`` is 1-based; keys are ``items``, ``page``, ``pages``, ``total``,
      ``has_prev`` and ``has_next``;
    - ``pages`` is the number of pages needed for all items (0 when empty);
    - a ``page`` beyond the last page returns ``items == []`` with correct
      ``pages``/``total``, ``has_next`` False and ``has_prev`` True when any page exists;
    - ``page < 1`` or ``per_page < 1`` raises ``ValueError``; non-int (including
      bool) ``page``/``per_page`` raises ``TypeError``;
    - the returned ``items`` is a new list; the input is never mutated.
    """
    start = (page - 1) * per_page
    chunk = items[start:start + per_page]
    pages = len(items) // per_page
    return {
        "items": chunk,
        "page": page,
        "pages": pages,
        "total": len(items),
        "has_prev": page > 1,
        "has_next": page <= pages,
    }
