import importlib.util
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("stable_unique", root / "stable_unique.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

source = [3, 1, 3, 2, 1]
copy = list(source)
assert module.unique(source) == [3, 1, 2]
assert source == copy
assert module.unique([{"a": 1}, {"a": 1}, {"a": 2}]) == [{"a": 1}, {"a": 2}]
assert module.unique([[1], [1], [2], [1]]) == [[1], [2]]
assert module.unique([]) == []
