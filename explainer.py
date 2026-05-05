"""
Step-by-Step Explainer Engine
==============================
Given a timeline entry (who ran, from when, to when) and the full
process list + algorithm name, this module generates a plain-English
explanation of WHY the scheduler made that exact decision.

This is the most educational feature — it bridges the gap between
"watching" the simulation and "understanding" it.
"""

from typing import List, Optional
from process import Process


def explain_step(
    step_index: int,
    timeline: list,
    all_processes: List[Process],
    algo: str,
    quantum: int = 3
) -> dict:
    """
    Returns a dict with:
      - headline : one bold sentence (what happened)
      - reason   : why the scheduler chose this process
      - detail   : deeper OS concept explanation
      - tip      : interesting observation or warning (optional)
      - ready_queue : list of pids that were available at this moment
    """
    if step_index >= len(timeline):
        return _done_message(all_processes, timeline)

    pid, start, end = timeline[step_index]
    duration = end - start

    # Build ready queue at this moment — who had arrived but not finished
    finished_before = set()
    for i in range(step_index):
        p, s, e = timeline[i]
        if p != "IDLE":
            proc = _find_proc(all_processes, p)
            if proc and proc.finish_time is not None and proc.finish_time <= start:
                finished_before.add(p)

    ready_at_start = [
        p for p in all_processes
        if p.arrival_time <= start
        and p.pid not in finished_before
        and (p.finish_time is None or p.finish_time > start)
    ]

    # IDLE step
    if pid == "IDLE":
        next_pid = timeline[step_index + 1][0] if step_index + 1 < len(timeline) else "?"
        arrived_at_end = [p for p in all_processes if start < p.arrival_time <= end]
        return {
            "headline": f"CPU is IDLE from t={start} to t={end}",
            "reason": (
                f"No process has arrived yet at t={start}. "
                f"The CPU has nothing to run so it waits."
            ),
            "detail": (
                "In a real OS, idle time wastes CPU cycles. "
                "The OS kernel runs a special 'idle process' (PID 0 on Linux) "
                "to keep the CPU occupied with low-power instructions. "
                f"{next_pid} arrives at t={end} and will be picked next."
            ),
            "tip": (
                f"{', '.join(p.pid for p in arrived_at_end)} arrives during idle."
                if arrived_at_end else None
            ),
            "ready_queue": [],
            "pid": "IDLE",
            "start": start,
            "end": end,
        }

    proc = _find_proc(all_processes, pid)
    ready_names = [p.pid for p in ready_at_start]

    # ── FCFS ──────────────────────────────────────────────────────────────
    if algo == "FCFS":
        others = [p for p in ready_at_start if p.pid != pid]
        reason = (
            f"{pid} arrived at t={proc.arrival_time}, "
            f"which is earlier than all other ready processes "
            f"({', '.join(p.pid + ' (t=' + str(p.arrival_time) + ')' for p in others) if others else 'none'})."
            if others else
            f"{pid} is the only process that has arrived by t={start}."
        )
        detail = (
            "FCFS (First Come First Served) is non-preemptive — "
            "once a process starts it runs until completion. "
            "The ready queue is sorted strictly by arrival time."
        )
        tip = _convoy_tip(proc, ready_at_start)

    # ── SJF ───────────────────────────────────────────────────────────────
    elif algo == "SJF":
        others = sorted([p for p in ready_at_start if p.pid != pid],
                        key=lambda p: p.burst_time)
        reason = (
            f"{pid} has the shortest burst time ({proc.burst_time} units) "
            f"among all ready processes at t={start}."
            + (f" Others: {', '.join(p.pid + '=' + str(p.burst_time) for p in others)}."
               if others else "")
        )
        detail = (
            "SJF (Shortest Job First) picks the process with the least CPU time needed. "
            "This minimises average waiting time — proven to be optimal for non-preemptive scheduling. "
            "The catch: the OS can't actually know burst time in advance; "
            "real systems estimate it from past behaviour."
        )
        tip = _starvation_tip(proc, ready_at_start)

    # ── SRTF ──────────────────────────────────────────────────────────────
    elif algo == "SRTF":
        remaining = {p.pid: p.burst_time for p in all_processes}
        # subtract time already spent
        for i in range(step_index):
            pp, ss, ee = timeline[i]
            if pp != "IDLE" and pp in remaining:
                remaining[pp] -= (ee - ss)

        others_rem = {p.pid: remaining.get(p.pid, p.burst_time)
                      for p in ready_at_start if p.pid != pid}
        my_rem = remaining.get(pid, proc.burst_time)

        reason = (
            f"{pid} has the shortest REMAINING time ({my_rem} units) at t={start}."
            + (f" Others: {', '.join(k + '=' + str(v) for k,v in others_rem.items())}."
               if others_rem else "")
        )
        detail = (
            "SRTF (Shortest Remaining Time First) is the preemptive version of SJF. "
            "Every time a new process arrives, the scheduler checks if its burst time "
            "is less than the REMAINING time of the running process. "
            "If yes, a context switch happens immediately. "
            "This gives the best possible average waiting time but causes many context switches."
        )
        tip = (
            f"Context switch at t={start} — a new shorter job preempted the previous one."
            if step_index > 0 and timeline[step_index-1][0] not in ("IDLE", pid)
            else None
        )

    # ── Round Robin ───────────────────────────────────────────────────────
    elif algo == "Round Robin":
        is_full_quantum = duration == quantum
        reason = (
            f"{pid} is next in the circular ready queue at t={start}. "
            f"It runs for {duration} unit{'s' if duration > 1 else ''} "
            f"({'a full quantum of ' + str(quantum) if is_full_quantum else 'remaining burst — less than quantum'})."
        )
        remaining_after = proc.burst_time - sum(
            e - s for p, s, e in timeline[:step_index] if p == pid
        ) - duration
        detail = (
            f"Round Robin gives every process a fixed time slice (quantum = {quantum} units). "
            "After the quantum expires, the running process goes to the back of the queue "
            "and the next process gets its turn. "
            "This ensures fairness — no process waits more than (n-1)×quantum time units."
            + (f" {pid} still has {remaining_after} units remaining after this slice."
               if remaining_after > 0 else f" {pid} finishes in this slice.")
        )
        tip = (
            f"Quantum={quantum} is {'small — many context switches, but very responsive.' if quantum <= 3 else 'large — fewer switches but longer waits for short jobs.'}"
        )

    # ── Priority ──────────────────────────────────────────────────────────
    elif algo in ("Priority", "Priority + Aging"):
        others = sorted([p for p in ready_at_start if p.pid != pid],
                        key=lambda p: p.priority)
        reason = (
            f"{pid} has the highest priority (value={proc.priority}, lower = higher priority) "
            f"among all ready processes at t={start}."
            + (f" Others: {', '.join(p.pid + '(pri=' + str(p.priority) + ')' for p in others)}."
               if others else "")
        )
        detail = (
            "Priority Scheduling always picks the process with the lowest priority number. "
            "Lower number = more urgent (like Linux nice values: -20 is highest, +19 is lowest). "
            "Non-preemptive: once started, the process runs to completion even if a higher "
            "priority process arrives."
            + (" Priority Aging is active — processes waiting too long get their priority boosted automatically to prevent starvation."
               if algo == "Priority + Aging" else "")
        )
        tip = _starvation_tip(proc, ready_at_start)

    else:
        reason = f"{pid} was selected by the {algo} algorithm."
        detail = ""
        tip = None

    return {
        "headline": f"Running {pid}  (t={start} → t={end},  duration={duration})",
        "reason":   reason,
        "detail":   detail,
        "tip":      tip,
        "ready_queue": ready_names,
        "pid":      pid,
        "start":    start,
        "end":      end,
    }


def _done_message(processes, timeline):
    total = timeline[-1][2] if timeline else 0
    idle  = sum(e-s for p,s,e in timeline if p=="IDLE")
    util  = round((total-idle)/total*100, 1) if total else 0
    avg_w = round(sum(p.waiting_time for p in processes)/len(processes), 1) if processes else 0
    return {
        "headline": "Simulation complete!",
        "reason":   f"All {len(processes)} processes finished by t={total}.",
        "detail":   (
            f"CPU utilisation: {util}%   |   "
            f"Avg waiting time: {avg_w} units   |   "
            f"Idle time: {idle} units"
        ),
        "tip": "Go to the Comparison tab to see how other algorithms would have performed.",
        "ready_queue": [],
        "pid": "DONE",
        "start": total,
        "end": total,
    }


def _find_proc(processes, pid) -> Optional[Process]:
    return next((p for p in processes if p.pid == pid), None)


def _convoy_tip(proc, ready):
    """Warn if a long job is blocking short ones (convoy effect)."""
    short_waiters = [p for p in ready if p.pid != proc.pid and p.burst_time < proc.burst_time]
    if short_waiters and proc.burst_time >= 8:
        names = ", ".join(p.pid for p in short_waiters)
        return (
            f"Convoy effect: {names} (shorter jobs) must wait for {proc.pid} "
            f"(burst={proc.burst_time}). This is FCFS's main weakness."
        )
    return None


def _starvation_tip(proc, ready):
    """Warn if low-priority/long processes are being skipped repeatedly."""
    starving = [
        p for p in ready
        if p.pid != proc.pid and p.burst_time > proc.burst_time * 2
    ]
    if starving:
        names = ", ".join(p.pid for p in starving)
        return (
            f"Starvation risk: {names} keeps getting skipped. "
            "In a real OS, priority aging would boost their priority over time."
        )
    return None
