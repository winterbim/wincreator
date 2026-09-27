import importlib.util
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("table_row", root / "table_row.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

assert module.parse_row("| a | b |") == ["a", "b"]
assert module.parse_row(r"| a\|b | c |") == ["a|b", "c"]
assert module.parse_row(r"| C:\tmp | x |") == [r"C:\tmp", "x"]
assert module.parse_row("| | x |") == ["", "x"]
for value in ("a|b|", "|a|b", "plain"):
    try:
        module.parse_row(value)
    except ValueError:
        pass
    else:
        raise AssertionError("malformed row accepted")
