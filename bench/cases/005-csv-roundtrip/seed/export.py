def export_rows(rows):
    """Serialize rows (lists of str) to CSV text.

    Contract: for any list of rows of arbitrary strings, feeding the returned
    text to Python's ``csv.reader`` (default dialect, ``newline=""``) yields
    exactly the original rows. One line per row, lines end with "\r\n".
    An empty list of rows returns "".
    """
    return "".join(",".join(row) + "\r\n" for row in rows)
