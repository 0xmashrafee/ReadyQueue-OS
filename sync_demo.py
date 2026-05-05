"""
Synchronization Primitives Demo
================================
OS concepts demonstrated:
  - Mutex (Mutual Exclusion Lock): only one thread can hold it at a time
  - Semaphore: a counter that controls access to N slots
  - Producer/Consumer problem: classic bounded-buffer concurrency problem
  - Deadlock: two threads waiting for each other forever
  - Race condition: what happens WITHOUT synchronization

This module provides simulation data for the UI to animate.
No real threads are used — we simulate the timeline deterministically
so it can be replayed frame by frame in the visualizer.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from enum import Enum


class EventType(Enum):
    ACQUIRE     = "acquire"      # Thread successfully grabs the lock
    RELEASE     = "release"      # Thread releases the lock
    BLOCKED     = "blocked"      # Thread tries to acquire but lock is held
    UNBLOCKED   = "unblocked"    # Thread was waiting, now can proceed
    PRODUCE     = "produce"      # Producer adds item to buffer
    CONSUME     = "consume"      # Consumer takes item from buffer
    BUFFER_FULL = "buffer_full"  # Producer must wait — buffer is full
    BUFFER_EMPTY= "buffer_empty" # Consumer must wait — buffer is empty
    DEADLOCK    = "deadlock"     # Circular wait detected
    RACE        = "race"         # Race condition: unsynchronised write
    WAIT        = "wait"         # Thread doing work (holding lock)


@dataclass
class SyncEvent:
    time: int
    thread: str
    event: EventType
    resource: str
    detail: str = ""
    value: int = 0       # e.g. buffer level, counter value


# ── Mutex Simulation ──────────────────────────────────────────────────────────
def simulate_mutex(num_threads=3, work_duration=3) -> List[SyncEvent]:
    """
    Simulate N threads competing for a single mutex lock.
    Thread 0 arrives first, acquires the lock, does work, releases.
    Threads 1..N-1 are BLOCKED until the lock is free.
    This shows: mutual exclusion, blocking, and FIFO unlock order.
    """
    events = []
    t = 0
    lock_holder = None
    waiting = []

    thread_names = [f"T{i}" for i in range(num_threads)]

    # All threads "arrive" at time 0 and try to acquire
    for i, name in enumerate(thread_names):
        if i == 0:
            events.append(SyncEvent(t, name, EventType.ACQUIRE, "mutex",
                                    f"{name} acquired the lock", 0))
            lock_holder = name
            t += 1
        else:
            events.append(SyncEvent(t, name, EventType.BLOCKED, "mutex",
                                    f"{name} waiting — lock held by {lock_holder}", 0))
            waiting.append(name)
            t += 1

    # Lock holder does work for work_duration ticks
    for tick in range(work_duration):
        events.append(SyncEvent(t, lock_holder, EventType.WAIT, "mutex",
                                f"{lock_holder} in critical section (tick {tick+1}/{work_duration})", tick+1))
        t += 1

    # Release and hand off to next waiting thread
    while lock_holder or waiting:
        prev = lock_holder
        events.append(SyncEvent(t, prev, EventType.RELEASE, "mutex",
                                f"{prev} released the lock", 0))
        t += 1

        if waiting:
            next_thread = waiting.pop(0)
            events.append(SyncEvent(t, next_thread, EventType.UNBLOCKED, "mutex",
                                    f"{next_thread} unblocked — acquired lock", 0))
            lock_holder = next_thread
            t += 1

            for tick in range(work_duration):
                events.append(SyncEvent(t, lock_holder, EventType.WAIT, "mutex",
                                        f"{lock_holder} in critical section (tick {tick+1}/{work_duration})", tick+1))
                t += 1
        else:
            lock_holder = None
            break

    return events


# ── Producer/Consumer with Semaphore ─────────────────────────────────────────
def simulate_producer_consumer(buffer_size=5, num_produce=8, num_consume=6) -> List[SyncEvent]:
    """
    Classic bounded-buffer problem.
    Uses TWO semaphores (like real OSes):
      - 'empty' semaphore: counts empty slots (starts at buffer_size)
      - 'full'  semaphore: counts filled slots (starts at 0)
    Producer waits when buffer is FULL (empty semaphore = 0)
    Consumer waits when buffer is EMPTY (full semaphore = 0)
    This guarantees no overflow and no underflow.
    """
    events = []
    t = 0
    buffer = 0  # current fill level
    produced = 0
    consumed = 0

    prod_turn = True  # alternate producer/consumer

    while produced < num_produce or consumed < num_consume:
        if prod_turn and produced < num_produce:
            if buffer >= buffer_size:
                # Semaphore 'empty' = 0 → producer must wait
                events.append(SyncEvent(t, "Producer", EventType.BUFFER_FULL, "semaphore",
                                        f"Buffer full ({buffer}/{buffer_size}) — Producer waiting", buffer))
                t += 1
                # Consumer will run next to free space
                if consumed < num_consume and buffer > 0:
                    buffer -= 1
                    consumed += 1
                    events.append(SyncEvent(t, "Consumer", EventType.CONSUME, "semaphore",
                                            f"Consumed item #{consumed}  Buffer: {buffer}/{buffer_size}", buffer))
                    t += 1
            else:
                buffer += 1
                produced += 1
                events.append(SyncEvent(t, "Producer", EventType.PRODUCE, "semaphore",
                                        f"Produced item #{produced}  Buffer: {buffer}/{buffer_size}", buffer))
                t += 1
        elif not prod_turn and consumed < num_consume:
            if buffer <= 0:
                # Semaphore 'full' = 0 → consumer must wait
                events.append(SyncEvent(t, "Consumer", EventType.BUFFER_EMPTY, "semaphore",
                                        f"Buffer empty ({buffer}/{buffer_size}) — Consumer waiting", buffer))
                t += 1
                if produced < num_produce:
                    buffer += 1
                    produced += 1
                    events.append(SyncEvent(t, "Producer", EventType.PRODUCE, "semaphore",
                                            f"Produced item #{produced}  Buffer: {buffer}/{buffer_size}", buffer))
                    t += 1
            else:
                buffer -= 1
                consumed += 1
                events.append(SyncEvent(t, "Consumer", EventType.CONSUME, "semaphore",
                                        f"Consumed item #{consumed}  Buffer: {buffer}/{buffer_size}", buffer))
                t += 1
        else:
            # Drain remaining
            if produced < num_produce:
                if buffer < buffer_size:
                    buffer += 1
                    produced += 1
                    events.append(SyncEvent(t, "Producer", EventType.PRODUCE, "semaphore",
                                            f"Produced item #{produced}  Buffer: {buffer}/{buffer_size}", buffer))
                    t += 1
            if consumed < num_consume:
                if buffer > 0:
                    buffer -= 1
                    consumed += 1
                    events.append(SyncEvent(t, "Consumer", EventType.CONSUME, "semaphore",
                                            f"Consumed item #{consumed}  Buffer: {buffer}/{buffer_size}", buffer))
                    t += 1

        prod_turn = not prod_turn

    return events


# ── Deadlock Simulation ───────────────────────────────────────────────────────
def simulate_deadlock() -> List[SyncEvent]:
    """
    Classic two-thread deadlock:
      Thread A holds Lock 1, wants Lock 2
      Thread B holds Lock 2, wants Lock 1
      → circular wait → neither can proceed → DEADLOCK

    In real OSes, deadlock requires 4 conditions (Coffman conditions):
      1. Mutual exclusion   2. Hold and wait
      3. No preemption      4. Circular wait
    We demonstrate all 4 here.
    """
    events = []
    t = 0

    # Both threads acquire their first lock
    events.append(SyncEvent(t,   "Thread-A", EventType.ACQUIRE, "Lock-1",
                             "Thread-A acquired Lock-1", 0))
    events.append(SyncEvent(t+1, "Thread-B", EventType.ACQUIRE, "Lock-2",
                             "Thread-B acquired Lock-2", 0))
    t += 2

    # Both try to acquire the other's lock → BLOCKED
    events.append(SyncEvent(t,   "Thread-A", EventType.BLOCKED, "Lock-2",
                             "Thread-A waiting for Lock-2 (held by Thread-B)", 0))
    events.append(SyncEvent(t+1, "Thread-B", EventType.BLOCKED, "Lock-1",
                             "Thread-B waiting for Lock-1 (held by Thread-A)", 0))
    t += 2

    # Deadlock detected after timeout
    events.append(SyncEvent(t, "Thread-A", EventType.DEADLOCK, "Lock-1,Lock-2",
                             "DEADLOCK! Circular wait: A→Lock-2→B→Lock-1→A", 0))
    events.append(SyncEvent(t, "Thread-B", EventType.DEADLOCK, "Lock-1,Lock-2",
                             "DEADLOCK! OS must terminate one thread to recover", 0))

    return events


# ── Race Condition Demo ───────────────────────────────────────────────────────
def simulate_race_condition(steps=6) -> List[SyncEvent]:
    """
    Two threads increment a shared counter WITHOUT a mutex.
    Shows how interleaved reads/writes produce wrong results.
    Without sync: final value can be less than expected (lost updates).
    With mutex: each read-modify-write is atomic → correct result.
    """
    events = []
    t = 0
    counter = 0

    for i in range(steps):
        # Thread A reads (gets stale value)
        events.append(SyncEvent(t, "Thread-A", EventType.RACE, "counter",
                                f"A reads counter = {counter} (expects to write {counter+1})", counter))
        t += 1
        # Thread B ALSO reads same value before A writes
        events.append(SyncEvent(t, "Thread-B", EventType.RACE, "counter",
                                f"B reads counter = {counter} (expects to write {counter+1})", counter))
        t += 1
        # Both write — one update is LOST
        counter += 1  # Only increments once instead of twice
        events.append(SyncEvent(t, "Thread-A", EventType.RACE, "counter",
                                f"A writes {counter} — B's write overwrites same value! Lost update!", counter))
        t += 1
        events.append(SyncEvent(t, "Thread-B", EventType.RACE, "counter",
                                f"B writes {counter} — should be {(i+1)*2} by now!", counter))
        t += 1

    return events
