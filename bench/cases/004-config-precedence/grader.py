import importlib.util
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("config", root / "config.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

defaults = {"port": 8000, "debug": False, "name": "demo"}
file_cfg = {"port": 9000, "debug": True, "unknown": 1}
env = {"APP_PORT": "7000", "APP_DEBUG": "yes", "APP_NAME": "prod", "APP_UNKNOWN": "x"}
d0, f0, e0 = dict(defaults), dict(file_cfg), dict(env)
assert module.resolve(defaults, file_cfg, env) == {"port": 7000, "debug": True, "name": "prod"}
assert defaults == d0 and file_cfg == f0 and env == e0
assert module.resolve(defaults, {"name": "file"}, {})["name"] == "file"
assert module.resolve(defaults, {}, {}) == defaults
try:
    module.resolve(defaults, {}, {"APP_DEBUG": "maybe"})
except ValueError:
    pass
else:
    raise AssertionError("invalid bool must raise ValueError")
