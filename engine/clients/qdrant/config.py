import os
import random
import time

QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "benchmark")
QDRANT_MAX_OPTIMIZATION_THREADS = os.getenv("QDRANT_MAX_OPTIMIZATION_THREADS", None)


def retry_with_exponential_backoff(
    func, *args, max_retries=10, base_delay=1, max_delay=90, **kwargs
):
    retries = 0
    while retries < max_retries:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            delay = min(base_delay * 2**retries + random.uniform(0, 1), max_delay)
            time.sleep(delay)
            retries += 1
            print(f"received the following exception on try #{retries}: {e.__str__}")
            if retries == max_retries:
                raise e
            else:
                print("retrying...")
