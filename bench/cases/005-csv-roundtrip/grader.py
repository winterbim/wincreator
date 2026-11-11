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

import csv
import io

m = load("export")


def rt(rows):
    return list(csv.reader(io.StringIO(m.export_rows(rows), newline=""))) == rows


check("comma", lambda: rt([["1", "Doe, Jane"]]))
check("embedded quote", lambda: rt([["say \"hi\"", "x"]]))
check("embedded newline", lambda: rt([["line1\nline2", "x"]]))
check("embedded CRLF", lambda: rt([["a\r\nb", "c"]]))
check("leading/trailing space", lambda: rt([["  padded  ", ""]]))
check("quote and comma", lambda: rt([['a,"b",c', '"']]))
check("empty rows list", lambda: m.export_rows([]) == "")
check("CRLF terminator", lambda: m.export_rows([["a", "b"]]) == "a,b\r\n")
finish("trap", not failures, failures)
