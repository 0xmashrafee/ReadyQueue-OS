from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Process:
    pid: str
    burst_time: int
    arrival_time: int
    priority: int

    remaining_time: int = 0
    start_time: Optional[int] = None
    finish_time: Optional[int] = None
    waiting_time: int = 0
    turnaround_time: int = 0
    color: str = "#4A90D9"
    # For aging: track how much priority has been boosted
    aged_priority: int = 0

    def __post_init__(self):
        self.remaining_time = self.burst_time
        self.aged_priority = self.priority

    def compute_metrics(self):
        if self.finish_time is not None:
            self.turnaround_time = self.finish_time - self.arrival_time
            self.waiting_time = self.turnaround_time - self.burst_time

    @property
    def response_time(self) -> Optional[int]:
        if self.start_time is not None:
            return self.start_time - self.arrival_time
        return None


STARVATION_THRESHOLD = 10
