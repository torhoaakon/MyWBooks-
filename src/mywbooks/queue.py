import os

import dramatiq
from dramatiq.brokers.redis import RedisBroker

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
dramatiq.set_broker(RedisBroker(url=REDIS_URL))  # type: ignore[no-untyped-call]
