from retry import retry

calls = []


def flaky():
    calls.append(1)
    if len(calls) < 3:
        raise RuntimeError("boom")
    return "ok"


assert retry(flaky, attempts=3, base_delay=1, sleep=lambda s: None) == "ok"
assert len(calls) == 3
print("ok")
