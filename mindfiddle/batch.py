import os
from concurrent.futures import ThreadPoolExecutor

from mindfiddle._core import interpret


def default_thread_count():
    return os.cpu_count() or 1


class BatchEval:
    def __init__(self, jobs, num_threads=None):
        self.jobs = list(jobs)

        if num_threads is None:
            num_threads = default_thread_count()
        if num_threads < 1:
            raise ValueError("num_threads must be at least 1")

        calls = [
            (job["program"], job["data_tape"], job["max_steps"]) for job in self.jobs
        ]

        self.num_threads = min(num_threads, max(len(calls), 1))
        self._results = None
        self._executor = ThreadPoolExecutor(max_workers=self.num_threads)
        self._futures = [
            self._executor.submit(interpret, program, data_tape, max_steps)
            for program, data_tape, max_steps in calls
        ]

    def wait(self):
        if self._results is not None:
            return self._results
        try:
            self._results = [future.result() for future in self._futures]
        finally:
            self._executor.shutdown(wait=True)
        return self._results

    def __len__(self):
        return len(self.jobs)


def batch_eval_async(jobs, num_threads=None):
    return BatchEval(jobs, num_threads)
