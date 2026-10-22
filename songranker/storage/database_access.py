"""Allow normal concurrent DB use; drain connections during local maintenance."""

from contextlib import contextmanager
from threading import Condition, get_ident
import time


class MaintenanceGate:
    def __init__(self):
        self.condition = Condition()
        self.connections = 0
        self.owner = None

    def enter_connection(self, timeout=30):
        deadline = time.monotonic() + timeout
        with self.condition:
            while self.owner is not None and self.owner != get_ident():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('Database maintenance is in progress; try again shortly.')
                self.condition.wait(remaining)
            self.connections += 1

    def leave_connection(self):
        with self.condition:
            self.connections -= 1
            self.condition.notify_all()

    @contextmanager
    def maintenance(self, timeout=30):
        deadline = time.monotonic() + timeout
        with self.condition:
            if self.owner == get_ident():
                raise RuntimeError('Nested database maintenance is not supported.')
            while self.owner is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('Another database maintenance task is running.')
                self.condition.wait(remaining)
            self.owner = get_ident()
            try:
                while self.connections:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError('Database is still busy; maintenance was cancelled.')
                    self.condition.wait(remaining)
            except BaseException:
                self.owner = None
                self.condition.notify_all()
                raise
        try:
            yield
        finally:
            with self.condition:
                self.owner = None
                self.condition.notify_all()


gate = MaintenanceGate()
