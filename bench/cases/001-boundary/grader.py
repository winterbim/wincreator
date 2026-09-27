import importlib.util
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("eligibility", root / "eligibility.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

assert module.eligible(18) is True
assert module.eligible(17) is False
assert module.eligible(120) is True
assert module.eligible(-1) is False
for value in (True, False, "18", 18.0, None):
    try:
        module.eligible(value)
    except TypeError:
        pass
    else:
        raise AssertionError(f"{value!r} must raise TypeError")
