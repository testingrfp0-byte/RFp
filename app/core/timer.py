import time

class Timer:
    def __init__(self):
        self.start = time.time()
        self.last = self.start
        self.steps = {}

    def log(self, name: str):
        now = time.time()
        self.steps[name] = round(now - self.last, 3)
        self.last = now

    def total(self):
        return round(time.time() - self.start, 3)