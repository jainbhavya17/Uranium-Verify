"""Run: python -m uranium.worker [--once]. No API or browser can claim scanner success."""

import argparse
import signal
import threading

from .config import Settings
from .db import make_engine, session_factory
from .processing import run_one
from .processing_config import ProcessingPolicy
from .storage import LocalPrivateStorage


def main():
    args = argparse.ArgumentParser()
    args.add_argument("--once", action="store_true")
    args.add_argument("--queue", choices=["all", "documents", "reports", "notifications"], default="all")
    selected = args.parse_args()
    once = selected.once
    settings = Settings()
    settings.validate()
    policy = ProcessingPolicy()
    policy.validate(settings.environment)
    engine = make_engine(settings.database_url)
    factory = session_factory(engine)
    storage = LocalPrivateStorage(settings.storage_root)
    from .notifications import dispatch_one
    from .reports import run_report_one

    def safe_work(callback):
        try:
            return callback()
        except Exception as exc:
            # Exception classes identify an operational failure without logging document/provider data.
            import json

            print(json.dumps({"event": "WORKER_QUEUE_FAILURE", "error_type": type(exc).__name__}), flush=True)
            return False

    def notifications():
        worked = False
        for _ in range(50):
            if not safe_work(lambda: dispatch_one(factory)):
                break
            worked = True
        return worked

    def tick():
        work = False
        if selected.queue in {"all", "notifications"}:
            work = notifications() or work
        if selected.queue in {"all", "reports"}:
            work = safe_work(lambda: run_report_one(factory, storage)) or work
        if selected.queue in {"all", "documents"}:
            work = safe_work(lambda: run_one(factory, storage, policy)) or work
        if selected.queue == "all":
            work = notifications() or work
        return work

    if once:
        tick()
    else:
        stop = threading.Event()
        signal.signal(signal.SIGINT, lambda *_: stop.set())
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
        while not stop.is_set():
            try:
                worked = tick()
            except Exception:
                worked = False
            stop.wait(0.2 if worked else 1)
    engine.dispose()


if __name__ == "__main__":
    main()
