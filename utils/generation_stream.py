"""Consume model output without hiding worker failures or waiting forever."""
from queue import Empty
from threading import Event, Thread
from time import monotonic


def stream_generation(generate, kwargs, streamer, should_stop, timeout=None):
    """The streamer must have a short queue timeout; timeout limits idle time."""
    cancelled = Event()
    errors = []
    # A local stop flag stays set even if a later request resets global state.
    kwargs['stopping_criteria'].append(lambda *a, **k: cancelled.is_set())

    def worker():
        try:
            generate(**kwargs)
        except Exception as exc:
            errors.append(exc)
        finally:
            streamer.end()

    thread = Thread(target=worker, daemon=True)
    thread.start()
    last_output = monotonic()
    try:
        while not should_stop():
            if errors:
                raise errors[0]
            try:
                chunk = next(streamer)
            except Empty:
                if timeout is not None and monotonic() - last_output >= timeout:
                    raise TimeoutError('The language model stopped responding while creating the video prompt.')
                continue
            except StopIteration:
                if errors:
                    raise errors[0]
                break
            if chunk:
                last_output = monotonic()
                yield chunk
    finally:
        cancelled.set()
        thread.join(timeout=3.0)
