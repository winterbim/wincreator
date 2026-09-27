def _cells(line):
    if not (line.startswith("|") and line.endswith("|")):
        return None
    cells, cell, escaped = [], [], False
    for ch in line[1:-1]:
        if escaped:
            if ch == "|":
                cell.append("|")
            else:
                cell.extend(("\\", ch))
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == "|":
            cells.append("".join(cell).strip())
            cell = []
        else:
            cell.append(ch)
    if escaped:
        cell.append("\\")
    cells.append("".join(cell).strip())
    return cells


def parse_ledger(text):
    header = ["ID", "Level", "Claim", "Gate (what proves it)", "Status", "Evidence"]
    rows, state, fence = [], "seek", None

    for raw in text.splitlines():
        line = raw.strip()

        marker = "\x60\x60\x60" if line.startswith("\x60\x60\x60") else "~~~" if line.startswith("~~~") else None
        if marker:
            if fence is None:
                fence = marker
            elif fence == marker:
                fence = None
            continue
        if fence:
            continue

        cells = _cells(line)

        if state == "seek":
            if cells == header:
                state = "separator"
            continue

        if state == "separator":
            if not cells or len(cells) != 6 or not all(c and set(c) <= {"-", ":"} for c in cells):
                return []
            state = "rows"
            continue

        if not line or cells is None:
            break
        if len(cells) != 6:
            continue
        rows.append(dict(zip(("id", "level", "claim", "gate", "status", "evidence"), cells)))

    return rows
