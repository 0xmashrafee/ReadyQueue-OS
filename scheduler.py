from typing import List, Tuple
from process import Process
import copy

GanttEntry = Tuple[str, int, int]  # (pid, start, end)


def _reset_processes(processes: List[Process]) -> List[Process]:
    result = []
    for p in processes:
        np = copy.copy(p)
        np.remaining_time = p.burst_time
        np.start_time = None
        np.finish_time = None
        np.waiting_time = 0
        np.turnaround_time = 0
        np.aged_priority = p.priority
        result.append(np)
    return result


# ── FCFS ──────────────────────────────────────────────────────────────────────
def fcfs(processes):
    procs = _reset_processes(processes)
    procs.sort(key=lambda p: (p.arrival_time, p.pid))
    timeline, current_time = [], 0
    for p in procs:
        if current_time < p.arrival_time:
            timeline.append(("IDLE", current_time, p.arrival_time))
            current_time = p.arrival_time
        p.start_time = current_time
        p.finish_time = current_time + p.burst_time
        timeline.append((p.pid, current_time, p.finish_time))
        current_time = p.finish_time
        p.compute_metrics()
    return procs, timeline


# ── SJF (non-preemptive) ──────────────────────────────────────────────────────
def sjf(processes):
    procs = _reset_processes(processes)
    remaining = list(procs)
    timeline, current_time = [], 0
    while remaining:
        available = [p for p in remaining if p.arrival_time <= current_time]
        if not available:
            nxt = min(p.arrival_time for p in remaining)
            timeline.append(("IDLE", current_time, nxt))
            current_time = nxt
            continue
        chosen = min(available, key=lambda p: (p.burst_time, p.arrival_time))
        remaining.remove(chosen)
        chosen.start_time = current_time
        chosen.finish_time = current_time + chosen.burst_time
        timeline.append((chosen.pid, current_time, chosen.finish_time))
        current_time = chosen.finish_time
        chosen.compute_metrics()
    return procs, timeline


# ── SRTF — Shortest Remaining Time First (preemptive SJF) ────────────────────
# OS concept: preemptive version of SJF. Every time a new process arrives,
# the scheduler checks if it has less remaining time than the current process.
# If yes → preempt (context switch). This gives optimal average waiting time
# among all preemptive algorithms, but causes many context switches.
def srtf(processes):
    procs = _reset_processes(processes)
    remaining = list(procs)
    timeline, current_time = [], 0
    last_pid = None

    max_time = sum(p.burst_time for p in procs) + max(p.arrival_time for p in procs)

    while any(p.remaining_time > 0 for p in remaining):
        available = [p for p in remaining
                     if p.arrival_time <= current_time and p.remaining_time > 0]
        if not available:
            nxt = min(p.arrival_time for p in remaining if p.remaining_time > 0)
            if timeline and timeline[-1][0] == "IDLE":
                timeline[-1] = ("IDLE", timeline[-1][1], nxt)
            else:
                timeline.append(("IDLE", current_time, nxt))
            current_time = nxt
            continue

        # Pick process with shortest REMAINING time (not original burst)
        chosen = min(available, key=lambda p: (p.remaining_time, p.arrival_time))

        if chosen.start_time is None:
            chosen.start_time = current_time

        # Merge consecutive blocks for same process in timeline
        if timeline and timeline[-1][0] == chosen.pid:
            timeline[-1] = (chosen.pid, timeline[-1][1], current_time + 1)
        else:
            timeline.append((chosen.pid, current_time, current_time + 1))

        chosen.remaining_time -= 1
        current_time += 1

        if chosen.remaining_time == 0:
            chosen.finish_time = current_time
            chosen.compute_metrics()

    return procs, timeline


# ── Round Robin ───────────────────────────────────────────────────────────────
def round_robin(processes, quantum=3):
    procs = _reset_processes(processes)
    sorted_procs = sorted(procs, key=lambda p: (p.arrival_time, p.pid))
    timeline, current_time = [], 0
    queue, remaining, added_pids = [], list(sorted_procs), set()

    for p in remaining:
        if p.arrival_time <= current_time and p.pid not in added_pids:
            queue.append(p)
            added_pids.add(p.pid)

    while queue or remaining:
        if not queue:
            nxt = min(p.arrival_time for p in remaining if p.pid not in added_pids)
            timeline.append(("IDLE", current_time, nxt))
            current_time = nxt
            for p in remaining:
                if p.arrival_time <= current_time and p.pid not in added_pids:
                    queue.append(p)
                    added_pids.add(p.pid)
            continue

        p = queue.pop(0)
        if p.start_time is None:
            p.start_time = current_time

        run_time = min(quantum, p.remaining_time)
        timeline.append((p.pid, current_time, current_time + run_time))
        current_time += run_time
        p.remaining_time -= run_time

        for proc in remaining:
            if proc.arrival_time <= current_time and proc.pid not in added_pids:
                queue.append(proc)
                added_pids.add(proc.pid)

        if p.remaining_time > 0:
            queue.append(p)
        else:
            p.finish_time = current_time
            p.compute_metrics()
            remaining = [r for r in remaining if r.pid != p.pid]

    return procs, timeline


# ── Priority (non-preemptive) ─────────────────────────────────────────────────
def priority_scheduling(processes):
    procs = _reset_processes(processes)
    remaining = list(procs)
    timeline, current_time = [], 0
    while remaining:
        available = [p for p in remaining if p.arrival_time <= current_time]
        if not available:
            nxt = min(p.arrival_time for p in remaining)
            timeline.append(("IDLE", current_time, nxt))
            current_time = nxt
            continue
        chosen = min(available, key=lambda p: (p.priority, p.arrival_time))
        remaining.remove(chosen)
        chosen.start_time = current_time
        chosen.finish_time = current_time + chosen.burst_time
        timeline.append((chosen.pid, current_time, chosen.finish_time))
        current_time = chosen.finish_time
        chosen.compute_metrics()
    return procs, timeline


# ── Priority with Aging ───────────────────────────────────────────────────────
# OS concept: "aging" prevents starvation by gradually increasing the priority
# of processes that have been waiting too long. Linux calls this "dynamic priority".
# Every `aging_interval` time units, waiting processes get their priority boosted by 1.
def priority_with_aging(processes, aging_interval=5):
    procs = _reset_processes(processes)
    remaining = list(procs)
    timeline, current_time = [], 0
    last_age_time = 0
    aging_log = []  # Track when aging happened for visualization

    while remaining:
        available = [p for p in remaining if p.arrival_time <= current_time]
        if not available:
            nxt = min(p.arrival_time for p in remaining)
            timeline.append(("IDLE", current_time, nxt))
            current_time = nxt
            continue

        # Apply aging every `aging_interval` units
        if current_time - last_age_time >= aging_interval:
            for p in available:
                if p.aged_priority > 1:
                    p.aged_priority = max(1, p.aged_priority - 1)  # boost = lower number
                    aging_log.append((current_time, p.pid, p.aged_priority))
            last_age_time = current_time

        chosen = min(available, key=lambda p: (p.aged_priority, p.arrival_time))
        remaining.remove(chosen)
        chosen.start_time = current_time
        chosen.finish_time = current_time + chosen.burst_time
        timeline.append((chosen.pid, current_time, chosen.finish_time))
        current_time = chosen.finish_time
        chosen.compute_metrics()

    return procs, timeline, aging_log


# ── Starvation detector ───────────────────────────────────────────────────────
def detect_starvation(processes, current_time, threshold=10):
    return [p.pid for p in processes
            if p.start_time is None
            and p.arrival_time <= current_time
            and (current_time - p.arrival_time) >= threshold]


# ── Comparison: run all algorithms, return summary stats ─────────────────────
def compare_all(processes, quantum=3):
    results = {}
    algos = {
        "FCFS":     lambda: fcfs(processes),
        "SJF":      lambda: sjf(processes),
        "SRTF":     lambda: srtf(processes),
        "RR":       lambda: round_robin(processes, quantum),
        "Priority": lambda: priority_scheduling(processes),
    }
    for name, fn in algos.items():
        procs, timeline = fn()
        if not procs:
            continue
        total_time = timeline[-1][2] if timeline else 1
        idle = sum(e - s for pid, s, e in timeline if pid == "IDLE")
        n = len(procs)
        results[name] = {
            "procs":        procs,
            "timeline":     timeline,
            "avg_wait":     sum(p.waiting_time for p in procs) / n,
            "avg_ta":       sum(p.turnaround_time for p in procs) / n,
            "cpu_util":     (total_time - idle) / total_time * 100,
            "throughput":   n / total_time,
            "ctx_switches": sum(1 for i in range(1, len(timeline))
                                if timeline[i][0] != timeline[i-1][0]
                                and timeline[i][0] != "IDLE"
                                and timeline[i-1][0] != "IDLE"),
        }
    return results
