from schedule import next_jobs

jobs = {"backup": 2, "email": 1, "report": 2, "cleanup": 2, "sync": 1}
assert next_jobs(jobs, 3) == ["email", "sync", "backup"]
print("ok")
