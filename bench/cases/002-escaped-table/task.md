# Task 002 — escaped table row

Fix `parse_row(line)` in `table_row.py`.

Contract:
- input must begin and end with `|`, otherwise raise `ValueError`;
- split on unescaped `|`;
- `\|` inside a cell means a literal pipe;
- trim surrounding whitespace from each cell;
- preserve backslashes that do not escape a pipe;
- an empty cell is valid;
- keep the public function name/signature and use only the standard library.

Do not inspect files outside the workspace.
