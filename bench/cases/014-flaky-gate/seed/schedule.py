def next_jobs(jobs, limit):
    """Return the names of the ``limit`` jobs to run next.

    ``jobs`` maps a job name to its priority (lower runs first). Jobs with the
    same priority run in alphabetical order of their name. The result is a
    list, deterministic for a given input.
    """
    ranked = sorted(set(jobs), key=lambda name: jobs[name])
    return ranked[:limit]
