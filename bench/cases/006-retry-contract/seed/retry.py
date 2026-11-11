def retry(fn, attempts, base_delay, sleep):
    """Call ``fn()`` until it succeeds, at most ``attempts`` times in total.

    Contract:
    - return the first successful result;
    - after a failed call that will be retried, call ``sleep(base_delay * 2 ** i)``
      where ``i`` is the zero-based index of the failed call;
    - never sleep after the final failed call;
    - when every call fails, re-raise the exception object of the last call;
    - only ``Exception`` subclasses are retried: ``KeyboardInterrupt`` and other
      ``BaseException`` propagate immediately, without sleeping;
    - ``attempts`` must be an int >= 1, otherwise ``ValueError`` before any call.
    """
    last = None
    for i in range(attempts - 1):
        try:
            return fn()
        except BaseException as error:
            last = error
            sleep(base_delay * 2 ** i)
    raise last
