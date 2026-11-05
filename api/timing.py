import functools
import logging
import time

logger = logging.getLogger("linkpulse")


def timed(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.info("%s took %.1f ms", func.__name__, elapsed_ms)

    return wrapper
