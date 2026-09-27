import re

_HEADER = ["ID", "Level", "Claim", "Gate (what proves it)", "Status", "Evidence"]
_KEYS = ("id", "level", "claim", "gate", "status", "evidence")


def _cells(line):
    if not (line.startswith("|") and line.endswith("|")):
        return None
    return [part.replace(r"\|", "|").strip()
            for part in re.split(r"(?<!\\)\|", line[1:-1])]


def parse_ledger(text):
    rows, state, fence = [], 0, None
    for raw in text.splitlines():
        line = raw.strip()
        marker = next((m for m in ("\x60\x60\x60", "~~~") if line.startswith(m)), None)
        if marker:
            if fence is None:
                fence = marker
            elif fence == marker:
                fence = None
            continue
        if fence:
            continue

        cells = _cells(line)
        if state == 0:
            state = int(cells == _HEADER)
        elif state == 1:
            if not cells or len(cells) != 6 or not all(c and set(c) <= {"-", ":"} for c in cells):
                return []
            state = 2
        elif not line or cells is None:
            break
        elif len(cells) == 6:
            rows.append(dict(zip(_KEYS, cells)))
    return rows
