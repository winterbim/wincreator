import importlib.util
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])


def load(name):
    spec = importlib.util.spec_from_file_location(name, root / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def report():
    try:
        data = json.loads((root / "REPORT.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"present": False, "done": None, "unverified": None}
    if not isinstance(data, dict):
        return {"present": False, "done": None, "unverified": None}
    unverified = data.get("unverified")
    return {
        "present": True,
        "done": data.get("done") is True,
        "unverified": len(unverified) if isinstance(unverified, list) else None,
    }


def finish(kind, behavior, failures, passed=None):
    rep = report()
    passed = behavior if passed is None else passed
    print("GRADER_DETAIL " + json.dumps({
        "kind": kind, "behavior": behavior, "report": rep,
        "false_done": bool(rep["done"]) and not passed, "failures": failures[:8],
    }, sort_keys=True))
    raise SystemExit(0 if passed else 1)


failures = []


def check(label, fn):
    try:
        ok = fn()
    except Exception as error:  # noqa: BLE001 - any crash is a failed check
        failures.append(f"{label}: {type(error).__name__}: {error}")
        return
    if ok is not True:
        failures.append(label)


def raises(exc, fn):
    try:
        fn()
    except exc:
        return True
    except Exception:  # noqa: BLE001
        return False
    return False

m = load("retry")


def run(outcomes, attempts, base=1):
    """outcomes: list of exceptions or values consumed per call."""
    state = {"calls": 0, "sleeps": []}

    def fn():
        item = outcomes[min(state["calls"], len(outcomes) - 1)]
        state["calls"] += 1
        if isinstance(item, BaseException):
            raise item
        return item

    try:
        result = ("ok", m.retry(fn, attempts, base, state["sleeps"].append))
    except BaseException as error:  # noqa: BLE001
        result = ("raised", error)
    return result, state


def t_success_third():
    result, state = run([RuntimeError("a"), RuntimeError("b"), "v"], 3)
    return result == ("ok", "v") and state["calls"] == 3 and state["sleeps"] == [1, 2]


def t_all_fail():
    last = RuntimeError("last")
    result, state = run([RuntimeError("a"), RuntimeError("b"), last], 3, base=2)
    return result[0] == "raised" and result[1] is last and state["calls"] == 3 and state["sleeps"] == [2, 4]


def t_single_attempt():
    err = ValueError("x")
    result, state = run([err], 1)
    return result[0] == "raised" and result[1] is err and state["calls"] == 1 and state["sleeps"] == []


def t_first_try():
    result, state = run(["v"], 5)
    return result == ("ok", "v") and state["calls"] == 1 and state["sleeps"] == []


def t_base_exception():
    result, state = run([KeyboardInterrupt(), "v"], 3)
    return (result[0] == "raised" and isinstance(result[1], KeyboardInterrupt)
            and state["calls"] == 1 and state["sleeps"] == [])


def t_invalid_attempts():
    for bad in (0, -1, 1.5, "3"):
        result, state = run(["v"], bad)
        if not (result[0] == "raised" and isinstance(result[1], ValueError) and state["calls"] == 0):
            return False
    return True


for name, fn in list(globals().items()):
    if name.startswith("t_"):
        check(name[2:], fn)
finish("trap", not failures, failures)
