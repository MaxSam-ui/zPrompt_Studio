import unittest
from queue import Queue
from threading import Event
from utils.generation_stream import stream_generation


class Stream:
    def __init__(self):
        self.queue = Queue()

    def __next__(self):
        item = self.queue.get(timeout=0.01)
        if item is None:
            raise StopIteration
        return item

    def end(self):
        self.queue.put(None)


class GenerationStreamTests(unittest.TestCase):
    def test_output_is_streamed(self):
        stream = Stream()
        def generate(**kwargs):
            stream.queue.put('hello')
            stream.queue.put(' world')
        self.assertEqual(list(stream_generation(generate, {'stopping_criteria': []}, stream, lambda: False)), ['hello', ' world'])

    def test_worker_error_reaches_caller(self):
        def generate(**kwargs):
            raise RuntimeError('GPU failure')
        with self.assertRaisesRegex(RuntimeError, 'GPU failure'):
            list(stream_generation(generate, {'stopping_criteria': []}, Stream(), lambda: False))

    def test_idle_timeout_stops_worker(self):
        stopped = Event()
        def generate(**kwargs):
            while not kwargs['stopping_criteria'][-1]():
                stopped.wait(0.005)
            stopped.set()
        with self.assertRaises(TimeoutError):
            list(stream_generation(generate, {'stopping_criteria': []}, Stream(), lambda: False, timeout=0.03))
        self.assertTrue(stopped.is_set())

    def test_stop_while_no_tokens_arrive(self):
        stop = Event()
        finished = Event()
        def generate(**kwargs):
            stop.set()
            while not kwargs['stopping_criteria'][-1]():
                finished.wait(0.005)
            finished.set()
        self.assertEqual(list(stream_generation(generate, {'stopping_criteria': []}, Stream(), stop.is_set)), [])
        self.assertTrue(finished.is_set())


if __name__ == '__main__':
    unittest.main()
