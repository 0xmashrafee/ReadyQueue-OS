"""
PDF Export Module
==================
Generates a professional PDF report from a completed simulation.
Uses reportlab for all PDF rendering.

The report contains:
  1. Header  — title, algorithm, date/time
  2. Process table — all input processes
  3. Gantt chart  — drawn as colored rectangles (no screenshots needed)
  4. Metrics table — per-process results
  5. Summary stats — avg wait, turnaround, CPU util, throughput
  6. Algorithm explanation — what the algorithm does, pros/cons
"""

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm, mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, HRFlowable, KeepTogether)
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Group
from reportlab.graphics import renderPDF
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from datetime import datetime
from typing import List
import os

from process import Process

# ── Colour palette (matches the app's dark theme translated to print) ─────────
C_PURPLE   = colors.HexColor("#7C6AF7")
C_SUCCESS  = colors.HexColor("#2ECC71")
C_WARNING  = colors.HexColor("#E67E22")
C_DANGER   = colors.HexColor("#E74C3C")
C_INFO     = colors.HexColor("#3498DB")
C_DARK     = colors.HexColor("#1E1E2E")
C_PANEL    = colors.HexColor("#2A2A3E")
C_CARD     = colors.HexColor("#313148")
C_MUTED    = colors.HexColor("#9090A8")
C_TEXT     = colors.HexColor("#E8E8F0")
C_WHITE    = colors.white
C_IDLE     = colors.HexColor("#44475A")
C_LIGHT_BG = colors.HexColor("#F8F8FC")
C_BORDER   = colors.HexColor("#E0E0EC")

PROCESS_COLORS_HEX = [
    "#7C6AF7","#50FA7B","#FFB86C","#FF79C6",
    "#8BE9FD","#FF5555","#F1FA8C","#BD93F9"
]

ALGO_DESCRIPTIONS = {
    "FCFS": {
        "full": "First Come First Served",
        "how":  "Processes are executed in the exact order they arrive. The first process to arrive gets the CPU first and runs until completion.",
        "pros": "Simple to implement. No starvation. Predictable order.",
        "cons": "Convoy effect — short jobs stuck behind long ones. Poor average waiting time.",
        "use":  "Batch processing systems, print queues.",
    },
    "SJF": {
        "full": "Shortest Job First",
        "how":  "At each scheduling point, the process with the shortest burst time is selected. Non-preemptive — once started, a process runs to completion.",
        "pros": "Optimal average waiting time among non-preemptive algorithms.",
        "cons": "Starvation of long jobs. Burst time must be known or estimated in advance.",
        "use":  "Batch systems where job lengths are known.",
    },
    "SRTF": {
        "full": "Shortest Remaining Time First",
        "how":  "Preemptive version of SJF. Every time a new process arrives, the scheduler checks if its burst time is shorter than the current process's remaining time. If yes, context switch occurs.",
        "pros": "Optimal average waiting time overall. Best responsiveness for short jobs.",
        "cons": "High context switch overhead. Starvation possible. Requires knowing remaining burst time.",
        "use":  "Interactive systems needing fast response for short tasks.",
    },
    "Round Robin": {
        "full": "Round Robin",
        "how":  "Each process gets a fixed time slice (quantum). After the quantum expires the process goes to the back of the ready queue and the next process runs.",
        "pros": "Fair — every process gets equal CPU time. No starvation. Good response time.",
        "cons": "High context switching if quantum is too small. Poor throughput if quantum is too large.",
        "use":  "General-purpose OS time-sharing (Linux, Windows use variants of this).",
    },
    "Priority": {
        "full": "Priority Scheduling",
        "how":  "Each process has a priority number. The process with the lowest priority number (highest urgency) is always selected first. Non-preemptive.",
        "pros": "Important tasks run first. Flexible for real-time requirements.",
        "cons": "Starvation of low-priority processes. Priority inversion possible.",
        "use":  "Real-time systems, OS kernel tasks, interrupt handling.",
    },
    "Priority + Aging": {
        "full": "Priority Scheduling with Aging",
        "how":  "Same as Priority Scheduling but processes that wait too long automatically get their priority boosted (aged). This prevents starvation.",
        "pros": "Prevents starvation. Important tasks still run first.",
        "cons": "More complex. Priority values change over time.",
        "use":  "Modern general-purpose OS kernels (Linux dynamic priority).",
    },
}


def export_pdf(
    filepath: str,
    processes: List[Process],
    scheduled: List[Process],
    timeline: list,
    algo: str,
    quantum: int,
    aging_log: list = None,
) -> bool:
    """
    Main export function. Returns True on success, False on error.
    Uses landscape A4 for the Gantt chart to have more horizontal space.
    """
    try:
        doc = SimpleDocTemplate(
            filepath,
            pagesize=landscape(A4),
            leftMargin=1.5*cm, rightMargin=1.5*cm,
            topMargin=1.5*cm,  bottomMargin=1.5*cm,
            title="ReadyQueue — Simulation Report",
            author="ReadyQueue CPU Scheduler",
        )

        story = []
        styles = _build_styles()
        page_w = landscape(A4)[0] - 3*cm  # usable width

        # ── 1. Header ─────────────────────────────────────────────────────
        story += _build_header(styles, algo, quantum, aging_log)

        # ── 2. Input process table ────────────────────────────────────────
        story.append(Paragraph("Input Processes", styles["section"]))
        story.append(Spacer(1, 4*mm))
        story.append(_build_input_table(processes, styles))
        story.append(Spacer(1, 6*mm))

        # ── 3. Gantt chart ────────────────────────────────────────────────
        story.append(Paragraph("Gantt Chart", styles["section"]))
        story.append(Spacer(1, 4*mm))
        gantt = _build_gantt_drawing(timeline, processes, page_w)
        story.append(gantt)
        story.append(Spacer(1, 6*mm))

        # ── 4. Metrics table ──────────────────────────────────────────────
        story.append(Paragraph("Process Metrics", styles["section"]))
        story.append(Spacer(1, 4*mm))
        story.append(_build_metrics_table(scheduled, styles))
        story.append(Spacer(1, 6*mm))

        # ── 5. Summary stats ──────────────────────────────────────────────
        story.append(Paragraph("Summary Statistics", styles["section"]))
        story.append(Spacer(1, 4*mm))
        story.append(_build_summary_table(scheduled, timeline, styles, page_w))
        story.append(Spacer(1, 8*mm))

        # ── 6. Algorithm explanation ──────────────────────────────────────
        story.append(HRFlowable(width="100%", thickness=0.5,
                                color=C_BORDER, spaceAfter=4*mm))
        story += _build_algo_explanation(algo, styles)

        # ── Footer note ───────────────────────────────────────────────────
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph(
            "Generated by ReadyQueue  •  "
            f"{datetime.now().strftime('%B %d, %Y at %H:%M')}",
            styles["footer"]
        ))

        doc.build(story)
        return True

    except Exception as e:
        print(f"PDF export error: {e}")
        import traceback; traceback.print_exc()
        return False


# ── STYLES ────────────────────────────────────────────────────────────────────
def _build_styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title",
            fontSize=22, fontName="Helvetica-Bold",
            textColor=C_DARK, spaceAfter=2*mm, leading=26),
        "subtitle": ParagraphStyle("subtitle",
            fontSize=11, fontName="Helvetica",
            textColor=C_MUTED, spaceAfter=1*mm),
        "section": ParagraphStyle("section",
            fontSize=13, fontName="Helvetica-Bold",
            textColor=C_DARK, spaceBefore=2*mm, spaceAfter=1*mm,
            borderPad=2, leading=16),
        "body": ParagraphStyle("body",
            fontSize=10, fontName="Helvetica",
            textColor=C_DARK, leading=14),
        "body_muted": ParagraphStyle("body_muted",
            fontSize=9, fontName="Helvetica",
            textColor=C_MUTED, leading=13),
        "label": ParagraphStyle("label",
            fontSize=9, fontName="Helvetica-Bold",
            textColor=C_MUTED, spaceBefore=3*mm),
        "algo_name": ParagraphStyle("algo_name",
            fontSize=14, fontName="Helvetica-Bold",
            textColor=C_PURPLE, spaceAfter=2*mm),
        "pros": ParagraphStyle("pros",
            fontSize=10, fontName="Helvetica",
            textColor=colors.HexColor("#1A6B35"), leading=14),
        "cons": ParagraphStyle("cons",
            fontSize=10, fontName="Helvetica",
            textColor=colors.HexColor("#8B1A1A"), leading=14),
        "footer": ParagraphStyle("footer",
            fontSize=8, fontName="Helvetica",
            textColor=C_MUTED, alignment=TA_CENTER),
        "cell": ParagraphStyle("cell",
            fontSize=9, fontName="Helvetica",
            textColor=C_DARK, alignment=TA_CENTER),
        "cell_head": ParagraphStyle("cell_head",
            fontSize=9, fontName="Helvetica-Bold",
            textColor=C_WHITE, alignment=TA_CENTER),
    }


# ── HEADER ────────────────────────────────────────────────────────────────────
def _build_header(styles, algo, quantum, aging_log):
    algo_info = ALGO_DESCRIPTIONS.get(algo, {})
    full_name = algo_info.get("full", algo)

    elements = []
    # Title row
    elements.append(Paragraph("CPU Scheduler Visualizer — Simulation Report",
                               styles["title"]))

    sub_parts = [
        f"Algorithm: {algo} ({full_name})",
        f"Date: {datetime.now().strftime('%B %d, %Y  %H:%M')}",
    ]
    if algo == "Round Robin":
        sub_parts.insert(1, f"Time Quantum: {quantum} units")
    if aging_log:
        sub_parts.append(f"Aging applied: {len(aging_log)} time(s)")

    elements.append(Paragraph("  |  ".join(sub_parts), styles["subtitle"]))
    elements.append(HRFlowable(width="100%", thickness=1.5,
                               color=C_PURPLE, spaceAfter=6*mm))
    return elements


# ── INPUT TABLE ───────────────────────────────────────────────────────────────
def _build_input_table(processes, styles):
    headers = ["PID", "Burst Time", "Arrival Time", "Priority"]
    data = [headers]
    for p in processes:
        data.append([p.pid, str(p.burst_time), str(p.arrival_time), str(p.priority)])

    col_w = [3*cm, 3.5*cm, 3.5*cm, 3*cm]
    t = Table(data, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle([
        # Header
        ("BACKGROUND",  (0,0), (-1,0),  C_PANEL),
        ("TEXTCOLOR",   (0,0), (-1,0),  C_WHITE),
        ("FONTNAME",    (0,0), (-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",    (0,0), (-1,0),  9),
        ("ALIGN",       (0,0), (-1,-1), "CENTER"),
        ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [C_WHITE, C_LIGHT_BG]),
        ("FONTSIZE",    (0,1), (-1,-1), 9),
        ("FONTNAME",    (0,1), (-1,-1), "Helvetica"),
        ("GRID",        (0,0), (-1,-1), 0.3, C_BORDER),
        ("TOPPADDING",  (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
    ]))
    return t


# ── GANTT CHART DRAWING ───────────────────────────────────────────────────────
def _build_gantt_drawing(timeline, processes, page_w):
    if not timeline:
        return Spacer(1, 1*cm)

    max_time  = timeline[-1][2]
    row_map   = {}
    row_cols  = {}
    row_idx   = 0
    for pid, s, e in timeline:
        if pid != "IDLE" and pid not in row_map:
            proc = next((p for p in processes if p.pid == pid), None)
            row_map[pid]  = row_idx
            raw_col = proc.color if proc else "#7C6AF7"
            row_cols[pid] = colors.HexColor(raw_col)
            row_idx += 1

    n_rows    = max(len(row_map), 1)
    ROW_H     = 22          # px per process row
    LABEL_W   = 44          # left margin for pid labels
    AXIS_H    = 18          # height for time axis
    PADDING   = 8           # top/bottom padding
    chart_h   = n_rows * ROW_H + AXIS_H + PADDING * 2
    chart_w   = float(page_w)

    # Scale: map time units → pixels
    usable_w  = chart_w - LABEL_W - 10
    scale     = usable_w / max(max_time, 1)

    d = Drawing(chart_w, chart_h)

    # Background
    d.add(Rect(0, 0, chart_w, chart_h,
               fillColor=colors.HexColor("#F8F8FC"),
               strokeColor=C_BORDER, strokeWidth=0.5))

    # Draw each timeline block
    for pid, start, end in timeline:
        if pid == "IDLE":
            x  = LABEL_W + start * scale
            bw = (end - start) * scale
            y_top  = PADDING
            b_h    = n_rows * ROW_H
            d.add(Rect(x, chart_h - PADDING - b_h, bw, b_h,
                       fillColor=colors.HexColor("#DCDCE8"),
                       strokeColor=None))
            if bw > 20:
                d.add(String(x + bw/2, chart_h - PADDING - b_h/2 - 4,
                             "IDLE", fontSize=7,
                             fillColor=C_MUTED, textAnchor="middle"))
        else:
            r     = row_map.get(pid, 0)
            color = row_cols.get(pid, C_PURPLE)
            x     = LABEL_W + start * scale
            bw    = (end - start) * scale
            y     = chart_h - PADDING - (r + 1) * ROW_H
            # Block
            d.add(Rect(x, y, bw, ROW_H - 2,
                       fillColor=color, strokeColor=colors.white,
                       strokeWidth=0.5))
            # Duration label inside block
            if bw > 16:
                d.add(String(x + bw/2, y + ROW_H/2 - 5,
                             str(end - start),
                             fontSize=7, fontName="Helvetica-Bold",
                             fillColor=colors.white, textAnchor="middle"))

    # Row labels (PID tags on left)
    for pid, r in row_map.items():
        color = row_cols.get(pid, C_PURPLE)
        y = chart_h - PADDING - (r + 1) * ROW_H
        d.add(Rect(2, y, LABEL_W - 4, ROW_H - 2,
                   fillColor=colors.HexColor("#EEEDFE"),
                   strokeColor=color, strokeWidth=0.8))
        d.add(String(LABEL_W/2, y + ROW_H/2 - 5,
                     pid, fontSize=8, fontName="Helvetica-Bold",
                     fillColor=colors.HexColor("#534AB7"), textAnchor="middle"))

    # Time axis
    axis_y = PADDING + AXIS_H - 4
    d.add(Line(LABEL_W, axis_y, chart_w - 4, axis_y,
               strokeColor=C_MUTED, strokeWidth=0.5))

    tick_step = max(1, max_time // 20)
    for t in range(0, max_time + 1, tick_step):
        x = LABEL_W + t * scale
        d.add(Line(x, axis_y, x, axis_y - 4,
                   strokeColor=C_MUTED, strokeWidth=0.4))
        d.add(String(x, axis_y - 12, str(t),
                     fontSize=6, fillColor=C_MUTED, textAnchor="middle"))

    return d


# ── METRICS TABLE ─────────────────────────────────────────────────────────────
def _build_metrics_table(scheduled, styles):
    headers = ["PID", "Burst", "Arrival", "Priority",
               "Start", "Finish", "Waiting", "Turnaround", "Response"]
    data = [headers]

    for p in scheduled:
        rt = str(p.response_time) if p.response_time is not None else "—"
        is_starving = p.waiting_time >= 10
        row = [p.pid, str(p.burst_time), str(p.arrival_time), str(p.priority),
               str(p.start_time), str(p.finish_time),
               str(p.waiting_time), str(p.turnaround_time), rt]
        data.append(row)

    n = len(scheduled)
    col_w = [2*cm, 2*cm, 2.2*cm, 2.2*cm, 2*cm, 2.2*cm, 2.4*cm, 2.8*cm, 2.4*cm]

    t = Table(data, colWidths=col_w, repeatRows=1)
    style_cmds = [
        ("BACKGROUND",   (0,0),  (-1,0),  C_PANEL),
        ("TEXTCOLOR",    (0,0),  (-1,0),  C_WHITE),
        ("FONTNAME",     (0,0),  (-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",     (0,0),  (-1,-1), 8),
        ("ALIGN",        (0,0),  (-1,-1), "CENTER"),
        ("VALIGN",       (0,0),  (-1,-1), "MIDDLE"),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [C_WHITE, C_LIGHT_BG]),
        ("FONTNAME",     (0,1),  (-1,-1), "Helvetica"),
        ("GRID",         (0,0),  (-1,-1), 0.3, C_BORDER),
        ("TOPPADDING",   (0,0),  (-1,-1), 4),
        ("BOTTOMPADDING",(0,0),  (-1,-1), 4),
    ]

    # Highlight starving rows in red
    for i, p in enumerate(scheduled, start=1):
        if p.waiting_time >= 10:
            style_cmds.append(("BACKGROUND", (0,i), (-1,i),
                                colors.HexColor("#FFF0F0")))
            style_cmds.append(("TEXTCOLOR",  (6,i), (6,i),
                                colors.HexColor("#CC0000")))

    t.setStyle(TableStyle(style_cmds))
    return t


# ── SUMMARY STATS ─────────────────────────────────────────────────────────────
def _build_summary_table(scheduled, timeline, styles, page_w):
    if not scheduled or not timeline:
        return Spacer(1, 1*cm)

    total_t = timeline[-1][2]
    idle    = sum(e - s for pid, s, e in timeline if pid == "IDLE")
    n       = len(scheduled)
    avg_w   = sum(p.waiting_time      for p in scheduled) / n
    avg_ta  = sum(p.turnaround_time   for p in scheduled) / n
    cpu_u   = (total_t - idle) / total_t * 100 if total_t else 0
    thru    = n / total_t if total_t else 0
    ctx     = sum(1 for i in range(1, len(timeline))
                  if timeline[i][0] != timeline[i-1][0]
                  and timeline[i][0]   != "IDLE"
                  and timeline[i-1][0] != "IDLE")

    stats = [
        ("Avg Waiting Time",     f"{avg_w:.2f} units"),
        ("Avg Turnaround Time",  f"{avg_ta:.2f} units"),
        ("CPU Utilisation",      f"{cpu_u:.1f}%"),
        ("Throughput",           f"{thru:.3f} processes/unit"),
        ("Total Time",           f"{total_t} units"),
        ("Idle Time",            f"{idle} units"),
        ("Context Switches",     str(ctx)),
        ("Processes",            str(n)),
    ]

    # Two-column grid layout
    rows = []
    for i in range(0, len(stats), 2):
        left  = stats[i]
        right = stats[i+1] if i+1 < len(stats) else ("", "")
        rows.append([left[0], left[1], right[0], right[1]])

    col_w = [5*cm, 4*cm, 5*cm, 4*cm]
    t = Table(rows, colWidths=col_w)
    t.setStyle(TableStyle([
        ("FONTNAME",     (0,0),  (-1,-1), "Helvetica"),
        ("FONTSIZE",     (0,0),  (-1,-1), 9),
        ("TEXTCOLOR",    (0,0),  (-1,-1), C_MUTED),
        ("FONTNAME",     (1,0),  (1,-1),  "Helvetica-Bold"),
        ("FONTNAME",     (3,0),  (3,-1),  "Helvetica-Bold"),
        ("TEXTCOLOR",    (1,0),  (1,-1),  C_DARK),
        ("TEXTCOLOR",    (3,0),  (3,-1),  C_DARK),
        ("FONTSIZE",     (1,0),  (1,-1),  11),
        ("FONTSIZE",     (3,0),  (3,-1),  11),
        ("ALIGN",        (0,0),  (-1,-1), "LEFT"),
        ("VALIGN",       (0,0),  (-1,-1), "MIDDLE"),
        ("TOPPADDING",   (0,0),  (-1,-1), 5),
        ("BOTTOMPADDING",(0,0),  (-1,-1), 5),
        ("LINEBELOW",    (0,0),  (-1,-2), 0.3, C_BORDER),
        ("LINEBEFORE",   (2,0),  (2,-1),  0.5, C_BORDER),
    ]))
    return t


# ── ALGORITHM EXPLANATION ─────────────────────────────────────────────────────
def _build_algo_explanation(algo, styles):
    info = ALGO_DESCRIPTIONS.get(algo, {})
    if not info:
        return []

    elements = []
    elements.append(Paragraph("Algorithm Reference", styles["section"]))
    elements.append(Paragraph(f"{algo} — {info.get('full', '')}", styles["algo_name"]))
    elements.append(Paragraph(f"How it works: {info.get('how', '')}", styles["body"]))
    elements.append(Spacer(1, 3*mm))

    pros_cons = [
        [Paragraph("Advantages", styles["label"]),
         Paragraph("Disadvantages", styles["label"])],
        [Paragraph(info.get("pros",""), styles["pros"]),
         Paragraph(info.get("cons",""), styles["cons"])],
    ]
    pc_table = Table(pros_cons, colWidths=["50%","50%"])
    pc_table.setStyle(TableStyle([
        ("VALIGN",      (0,0), (-1,-1), "TOP"),
        ("TOPPADDING",  (0,0), (-1,-1), 4),
        ("LINEBEFORE",  (1,0), (1,-1),  0.5, C_BORDER),
        ("LEFTPADDING", (1,0), (1,-1),  8),
    ]))
    elements.append(pc_table)
    elements.append(Spacer(1, 3*mm))
    elements.append(Paragraph(
        f"Real-world use: {info.get('use','')}", styles["body_muted"]))
    return elements
