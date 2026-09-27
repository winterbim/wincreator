def parse_ledger(text):
    rows = []
    in_ledger = False
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("| ID | Level | Claim | Gate") and "Status" in line and "Evidence" in line:
            in_ledger = True
            continue
        if in_ledger and line.startswith("|----"):
            continue
        if in_ledger:
            if not line.startswith("|") or not line.endswith("|"):
                break
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) == 6:
                rows.append({
                    "id": cells[0],
                    "level": cells[1],
                    "claim": cells[2],
                    "gate": cells[3],
                    "status": cells[4],
                    "evidence": cells[5],
                })
    return rows
