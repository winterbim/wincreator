def parse_row(line):
    if not line.startswith("|") or not line.endswith("|"):
        raise ValueError("bad row")
    return [cell.strip() for cell in line[1:-1].split("|")]
