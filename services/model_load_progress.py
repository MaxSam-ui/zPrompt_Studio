"""Stream preparation status while a blocking model loader runs."""
from pathlib import Path
from queue import Queue, Empty
from threading import Thread
from time import monotonic

from utils.vlm_status import VLMStatus


def load_with_progress(load, model, cache_dir, texts, interval=1.0):
    messages = Queue()
    result = {}
    started = monotonic()
    phase = "vlm_cache_check"
    blobs = Path(cache_dir) / ("models--" + model.replace("/", "--")) / "blobs"
    baseline = {}
    if blobs.exists():
        baseline = {p.name: p.stat().st_size for p in blobs.glob("*.incomplete") if p.is_file()}

    def worker():
        try:
            result["value"] = load(model, progress=messages.put)
        except BaseException as exc:
            result["error"] = exc
        finally:
            messages.put(None)

    thread = Thread(target=worker, daemon=True)
    thread.start()
    try:
        while True:
            try:
                update = messages.get(timeout=interval)
                if update is None:
                    break
                phase = update
            except Empty:
                pass
            elapsed = int(monotonic() - started)
            active = []
            try:
                for path in blobs.glob("*.incomplete"):
                    size = path.stat().st_size
                    if path.name not in baseline or size != baseline[path.name]:
                        active.append(size)
            except OSError:
                pass  # A completed download can rename a file during this scan.
            if active:
                label = texts.get("vlm_downloading", "Downloading model files")
                detail = f"{sum(active) / 1024**3:.2f} GB"
            else:
                label = texts.get(phase, "Preparing model")
                detail = ""
            yield VLMStatus(f"⏳ {label} · {elapsed}s" + (f" · {detail}" if detail else ""))
    finally:
        # Never leave a loader mutating shared model state after the request ends.
        thread.join()
    if "error" in result:
        raise result["error"]
    return result["value"]
