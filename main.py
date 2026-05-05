import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import List, Optional
import math
import json
import os

from process import Process, STARVATION_THRESHOLD
from scheduler import (fcfs, sjf, srtf, round_robin, priority_scheduling,
                       priority_with_aging, detect_starvation, compare_all, GanttEntry)
from sync_demo import (simulate_mutex, simulate_producer_consumer,
                       simulate_deadlock, simulate_race_condition, EventType)
from explainer import explain_step
from pdf_export import export_pdf

# ── ReadyQueue Palette ────────────────────────────────────────────────────────
BG_DARK      = "#0D1117"   # deep navy-black
PANEL_BG     = "#161B22"   # dark panel
CARD_BG      = "#21262D"   # card surface
ACCENT       = "#00E5FF"   # cyan — the ReadyQueue brand colour
ACCENT2      = "#7B2FBE"   # purple secondary
ACCENT_HOVER = "#33EEFF"
TEXT_PRIMARY = "#E6EDF3"
TEXT_MUTED   = "#7D8590"
SUCCESS      = "#3FB950"
WARNING      = "#D29922"
DANGER       = "#F85149"
INFO         = "#58A6FF"
IDLE_COLOR   = "#30363D"
GANTT_HEIGHT = 46

# Vivid process colours — high contrast on dark bg
PROCESS_COLORS = ["#00E5FF","#3FB950","#FF7B72","#D2A8FF",
                  "#FFA657","#79C0FF","#56D364","#F78166"]

ALGO_LIST = ["FCFS","SJF","SRTF","Round Robin","Priority","Priority + Aging"]


class CPUSchedulerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ReadyQueue — CPU Scheduler")
        self.root.configure(bg=BG_DARK)
        self.root.resizable(True, True)
        # Open maximized so everything is visible on any screen size
        self.root.after(0, lambda: self.root.state("zoomed"))

        self.processes: List[Process] = []
        self.timeline   = []
        self.scheduled_processes = []
        self.animation_job = None
        self.current_frame = 0
        self.is_playing = False
        self.quantum_var  = tk.IntVar(value=3)
        self.color_index  = 0
        self.aging_log    = []

        # Step-by-step mode state
        self.step_mode    = False   # True = manual stepping, False = auto-play
        self.step_explanation = {}  # Current step's explanation dict

        # Sync demo state
        self.sync_events  = []
        self.sync_frame   = 0
        self.sync_job     = None
        self.sync_playing = False

        self._build_ui()
        self._add_sample_processes()

    def _tick_clock(self):
        """Live clock in the top bar — updates every second."""
        import datetime
        now = datetime.datetime.now().strftime("%A, %d %b %Y    %I:%M:%S %p")
        if hasattr(self, "_clock_label"):
            self._clock_label.config(text=now)
        self.root.after(1000, self._tick_clock)

        # ── TOP-LEVEL UI ──────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Top bar ────────────────────────────────────────────────────────────
        topbar = tk.Frame(self.root, bg=PANEL_BG, height=62)
        topbar.pack(fill=tk.X)
        topbar.pack_propagate(False)

        # Left — glowing cyan dot + RQ badge + name stack
        left_bar = tk.Frame(topbar, bg=PANEL_BG)
        left_bar.pack(side=tk.LEFT, padx=(18, 0), pady=0, fill=tk.Y)

        # Cyan accent bar (left edge)
        accent_bar = tk.Frame(topbar, bg=ACCENT, width=3)
        accent_bar.place(x=0, y=0, relheight=1)

        # RQ logo box — rounded feel via padding
        logo_box = tk.Frame(left_bar, bg=ACCENT, width=42, height=42)
        logo_box.pack(side=tk.LEFT, pady=10)
        logo_box.pack_propagate(False)
        tk.Label(logo_box, text="RQ", bg=ACCENT, fg=BG_DARK,
                 font=("Helvetica",14,"bold")).place(relx=.5, rely=.5, anchor="center")

        # Name + tagline
        name_frame = tk.Frame(left_bar, bg=PANEL_BG)
        name_frame.pack(side=tk.LEFT, padx=(12, 0), pady=0)
        tk.Label(name_frame, text="ReadyQueue",
                 bg=PANEL_BG, fg=ACCENT,
                 font=("Helvetica",18,"bold")).pack(anchor=tk.W)
        tk.Label(name_frame, text="CPU Process Scheduler  &  Sync Visualizer",
                 bg=PANEL_BG, fg=TEXT_MUTED,
                 font=("Helvetica",9)).pack(anchor=tk.W)

        # Right — live clock only, clean
        right_bar = tk.Frame(topbar, bg=PANEL_BG)
        right_bar.pack(side=tk.RIGHT, padx=20, pady=0, fill=tk.Y)

        self._clock_label = tk.Label(right_bar, text="",
                                     bg=PANEL_BG, fg=TEXT_MUTED,
                                     font=("Helvetica",9))
        self._clock_label.pack(side=tk.RIGHT, pady=(20,0))
        self._tick_clock()

        # Thin cyan bottom border on topbar
        tk.Frame(self.root, bg=ACCENT, height=2).pack(fill=tk.X)

        # ── Tab bar ────────────────────────────────────────────────────────────
        self.tab_var = tk.StringVar(value="Scheduler")
        tab_bar = tk.Frame(self.root, bg=BG_DARK, height=44)
        tab_bar.pack(fill=tk.X)
        tab_bar.pack_propagate(False)

        tab_icons = {
            "Scheduler":      "⚡  Scheduler",
            "Comparison":     "⚖  Comparison",
            "Synchronization":"🔒  Synchronization",
        }
        for tab, label in tab_icons.items():
            btn = tk.Button(tab_bar, text=label, bg=BG_DARK, fg=TEXT_MUTED,
                            relief=tk.FLAT, font=("Helvetica",10,"bold"),
                            cursor="hand2", borderwidth=0,
                            activebackground=CARD_BG, activeforeground=ACCENT,
                            padx=20, pady=10,
                            command=lambda t=tab: self._switch_tab(t))
            btn.pack(side=tk.LEFT)
            setattr(self, f"tab_btn_{tab}", btn)

        tk.Frame(self.root, bg=CARD_BG, height=1).pack(fill=tk.X)

        # Page container
        self.page_frame = tk.Frame(self.root, bg=BG_DARK)
        self.page_frame.pack(fill=tk.BOTH, expand=True)

        self.pages = {}
        for tab in ["Scheduler", "Comparison", "Synchronization"]:
            frame = tk.Frame(self.page_frame, bg=BG_DARK)
            self.pages[tab] = frame

        self._build_scheduler_page(self.pages["Scheduler"])
        self._build_comparison_page(self.pages["Comparison"])
        self._build_sync_page(self.pages["Synchronization"])
        self._switch_tab("Scheduler")

        # ── Status bar ─────────────────────────────────────────────────────
        status_bar = tk.Frame(self.root, bg=PANEL_BG, height=26)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        status_bar.pack_propagate(False)
        tk.Label(status_bar, text="ReadyQueue  •  Built with Python + tkinter",
                 bg=PANEL_BG, fg=TEXT_MUTED,
                 font=("Helvetica",8)).pack(side=tk.LEFT, padx=14, pady=5)
        self.status_msg = tk.Label(status_bar, text="Ready — add processes and run a simulation",
                                   bg=PANEL_BG, fg=ACCENT,
                                   font=("Helvetica",8))
        self.status_msg.pack(side=tk.RIGHT, padx=14, pady=5)

    def _switch_tab(self, name):
        for tab, frame in self.pages.items():
            frame.pack_forget()
        self.pages[name].pack(fill=tk.BOTH, expand=True)
        for tab in ["Scheduler", "Comparison", "Synchronization"]:
            btn = getattr(self, f"tab_btn_{tab}")
            if tab == name:
                btn.config(bg=CARD_BG, fg=ACCENT,
                           font=("Helvetica",10,"bold"),
                           relief=tk.FLAT)
            else:
                btn.config(bg=BG_DARK, fg=TEXT_MUTED,
                           font=("Helvetica",10,"bold"),
                           relief=tk.FLAT)

    # ═════════════════════════════════════════════════════════════════════════
    # TAB 1: SCHEDULER
    # ═════════════════════════════════════════════════════════════════════════
    def _build_scheduler_page(self, parent):
        main = tk.Frame(parent, bg=BG_DARK)
        main.pack(fill=tk.BOTH, expand=True)

        left = tk.Frame(main, bg=PANEL_BG, width=295)
        left.pack(side=tk.LEFT, fill=tk.Y)
        left.pack_propagate(False)
        self._build_left_panel(left)

        right = tk.Frame(main, bg=BG_DARK)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._build_right_panel(right)

    def _build_left_panel(self, parent):
        # Algorithm
        tk.Label(parent, text="⚡  ALGORITHM", bg=PANEL_BG, fg=ACCENT,
                 font=("Helvetica",10,"bold")).pack(anchor=tk.W, padx=16, pady=(18,4))

        self.algo_var = tk.StringVar(value="FCFS")
        algo_display = [
            ("FCFS — First Come First Served", "FCFS"),
            ("SJF — Shortest Job First",       "SJF"),
            ("SRTF — Shortest Remaining Time", "SRTF"),
            ("Round Robin (preemptive)",        "Round Robin"),
            ("Priority Scheduling",             "Priority"),
            ("Priority + Aging (anti-starvation)","Priority + Aging"),
        ]
        for label, val in algo_display:
            tk.Radiobutton(parent, text=label, variable=self.algo_var, value=val,
                           bg=PANEL_BG, fg=TEXT_PRIMARY, selectcolor=CARD_BG,
                           activebackground=PANEL_BG, activeforeground=TEXT_PRIMARY,
                           font=("Helvetica",10),
                           command=self._on_algo_change).pack(anchor=tk.W, padx=20, pady=1)

        # Quantum
        self.quantum_frame = tk.Frame(parent, bg=PANEL_BG)
        self.quantum_frame.pack(fill=tk.X, padx=16, pady=(4,0))
        tk.Label(self.quantum_frame, text="Time Quantum:", bg=PANEL_BG,
                 fg=TEXT_MUTED, font=("Helvetica",10)).pack(side=tk.LEFT)
        self.quantum_spinbox = tk.Spinbox(
            self.quantum_frame, from_=1, to=20, textvariable=self.quantum_var,
            width=4, bg=CARD_BG, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
            buttonbackground=CARD_BG, relief=tk.FLAT, font=("Helvetica",11))
        self.quantum_spinbox.pack(side=tk.LEFT, padx=8)
        self._on_algo_change()

        tk.Frame(parent, bg=CARD_BG, height=1).pack(fill=tk.X, padx=16, pady=12)

        # Add process form
        tk.Label(parent, text="＋  ADD PROCESS", bg=PANEL_BG, fg=ACCENT,
                 font=("Helvetica",10,"bold")).pack(anchor=tk.W, padx=16, pady=(0,6))

        form = tk.Frame(parent, bg=PANEL_BG)
        form.pack(fill=tk.X, padx=16)

        fields = [("PID","P1","pid_entry"),("Burst","5","burst_entry"),
                  ("Arrival","0","arrival_entry"),("Priority","1","priority_entry")]
        for label, default, attr in fields:
            row = tk.Frame(form, bg=PANEL_BG)
            row.pack(fill=tk.X, padx=4, pady=3)
            tk.Label(row, text=label, bg=PANEL_BG, fg=TEXT_MUTED,
                     font=("Helvetica",9), width=9, anchor=tk.W).pack(side=tk.LEFT)
            wrap = tk.Frame(row, bg=CARD_BG,
                            highlightbackground=CARD_BG, highlightthickness=1)
            wrap.pack(side=tk.LEFT, padx=(4,0))
            e = tk.Entry(wrap, bg=CARD_BG, fg=TEXT_PRIMARY,
                         insertbackground=ACCENT,
                         relief=tk.FLAT, font=("Helvetica",10), width=8)
            e.insert(0, default)
            e.pack(ipady=5, padx=5)
            e.bind("<FocusIn>",  lambda ev, w=wrap: w.config(highlightbackground=ACCENT))
            e.bind("<FocusOut>", lambda ev, w=wrap: w.config(highlightbackground=CARD_BG))
            setattr(self, attr, e)

        tk.Button(form, text="＋   Add Process", bg=ACCENT, fg=BG_DARK,
                  relief=tk.FLAT, font=("Helvetica",10,"bold"),
                  activebackground=ACCENT_HOVER, cursor="hand2",
                  command=self._add_process).pack(fill=tk.X, padx=4, pady=(8,10), ipady=8)

        tk.Frame(parent, bg=CARD_BG, height=1).pack(fill=tk.X, padx=16, pady=8)

        tk.Label(parent, text="☰  PROCESS QUEUE", bg=PANEL_BG, fg=ACCENT,
                 font=("Helvetica",10,"bold")).pack(anchor=tk.W, padx=16, pady=(0,4))

        self.proc_list_frame = tk.Frame(parent, bg=PANEL_BG)
        self.proc_list_frame.pack(fill=tk.BOTH, expand=True, padx=16)

        btns = tk.Frame(parent, bg=PANEL_BG)
        btns.pack(fill=tk.X, padx=16, pady=10)
        tk.Button(btns, text="▶   RUN SIMULATION", bg=ACCENT, fg=BG_DARK,
                  relief=tk.FLAT, font=("Helvetica",11,"bold"), cursor="hand2",
                  activebackground=ACCENT_HOVER, activeforeground=BG_DARK,
                  command=self._run_simulation).pack(fill=tk.X, ipady=10, pady=(0,6))
        tk.Button(btns, text="↺   Clear All", bg=CARD_BG, fg=TEXT_MUTED,
                  relief=tk.FLAT, font=("Helvetica",9), cursor="hand2",
                  activebackground=BG_DARK,
                  command=self._clear_all).pack(fill=tk.X, ipady=6)

        tk.Frame(btns, bg=CARD_BG, height=1).pack(fill=tk.X, pady=8)

        save_row = tk.Frame(btns, bg=PANEL_BG)
        save_row.pack(fill=tk.X, pady=(0,4))
        tk.Button(save_row, text="💾  Save Processes",
                  bg="#2A3A4A", fg="#8BE9FD", relief=tk.FLAT,
                  font=("Helvetica",10), cursor="hand2",
                  activebackground="#3A4A5A",
                  command=self._save_processes).pack(side=tk.LEFT, fill=tk.X,
                                                     expand=True, ipady=5, padx=(0,3))
        tk.Button(save_row, text="📂  Load",
                  bg="#2A3A4A", fg="#8BE9FD", relief=tk.FLAT,
                  font=("Helvetica",10), cursor="hand2",
                  activebackground="#3A4A5A",
                  command=self._load_processes).pack(side=tk.LEFT, ipady=5, ipadx=6)

        tk.Button(btns, text="📄  Export PDF Report",
                  bg="#2A2A3A", fg="#F1FA8C", relief=tk.FLAT,
                  font=("Helvetica",10,"bold"), cursor="hand2",
                  activebackground="#3A3A4A",
                  command=self._export_pdf).pack(fill=tk.X, ipady=6, pady=(4,0))

        self.recent_var = tk.StringVar(value="")
        self.recent_frame = tk.Frame(btns, bg=PANEL_BG)
        self.recent_frame.pack(fill=tk.X)
        self.recent_label = tk.Label(self.recent_frame, text="",
                                     bg=PANEL_BG, fg=TEXT_MUTED,
                                     font=("Helvetica",9), anchor=tk.W,
                                     wraplength=240)
        self.recent_label.pack(anchor=tk.W)

    def _build_right_panel(self, parent):
        # ── Top: controls bar (fixed, never scrolls) ──────────────────────
        hdr = tk.Frame(parent, bg=BG_DARK)
        hdr.pack(fill=tk.X, padx=20, pady=(10,4))
        tk.Label(hdr, text="▦  Gantt Chart", bg=BG_DARK, fg=ACCENT,
                 font=("Helvetica",13,"bold")).pack(side=tk.LEFT)
        self.time_label = tk.Label(hdr, text="", bg=BG_DARK, fg=TEXT_MUTED,
                                   font=("Helvetica",11))
        self.time_label.pack(side=tk.LEFT, padx=10)

        ctrl = tk.Frame(hdr, bg=BG_DARK)
        ctrl.pack(side=tk.RIGHT)
        self.play_btn = tk.Button(ctrl, text="▶ Play", bg=ACCENT, fg="white",
                                  relief=tk.FLAT, font=("Helvetica",10,"bold"),
                                  cursor="hand2", command=self._toggle_play)
        self.play_btn.pack(side=tk.LEFT, padx=3, ipady=4, ipadx=8)
        tk.Button(ctrl, text="⏮ Reset", bg=CARD_BG, fg=TEXT_MUTED, relief=tk.FLAT,
                  font=("Helvetica",10), cursor="hand2",
                  command=self._reset_animation).pack(side=tk.LEFT, padx=3, ipady=4, ipadx=8)
        self.step_btn = tk.Button(ctrl, text="👣 Step Mode: OFF",
                                  bg=CARD_BG, fg=TEXT_MUTED, relief=tk.FLAT,
                                  font=("Helvetica",10), cursor="hand2",
                                  command=self._toggle_step_mode)
        self.step_btn.pack(side=tk.LEFT, padx=3, ipady=4, ipadx=8)
        self.next_btn = tk.Button(ctrl, text="⏭ Next Step",
                                  bg="#534AB7", fg="white", relief=tk.FLAT,
                                  font=("Helvetica",10,"bold"), cursor="hand2",
                                  state=tk.DISABLED, command=self._next_step)
        self.next_btn.pack(side=tk.LEFT, padx=3, ipady=4, ipadx=8)
        self.prev_btn = tk.Button(ctrl, text="⏮ Prev",
                                  bg=CARD_BG, fg=TEXT_MUTED, relief=tk.FLAT,
                                  font=("Helvetica",10), cursor="hand2",
                                  state=tk.DISABLED, command=self._prev_step)
        self.prev_btn.pack(side=tk.LEFT, padx=3, ipady=4, ipadx=8)
        tk.Label(ctrl, text="Speed:", bg=BG_DARK, fg=TEXT_MUTED,
                 font=("Helvetica",10)).pack(side=tk.LEFT, padx=(10,3))
        self.speed_var = tk.IntVar(value=5)
        tk.Scale(ctrl, variable=self.speed_var, from_=1, to=10,
                 orient=tk.HORIZONTAL, bg=BG_DARK, fg=TEXT_MUTED,
                 troughcolor=CARD_BG, highlightthickness=0,
                 showvalue=False, length=80).pack(side=tk.LEFT)

        # Aging info bar (fixed, collapses when not needed)
        self.aging_bar = tk.Frame(parent, bg="#1A3A2A", height=0)
        self.aging_bar.pack(fill=tk.X, padx=20)
        self.aging_bar.pack_propagate(False)
        self.aging_info_label = tk.Label(self.aging_bar, text="", bg="#1A3A2A",
                                         fg=SUCCESS, font=("Helvetica",10))
        self.aging_info_label.pack(pady=5)

        # Starvation warning (fixed, collapses when not needed)
        self.starve_frame = tk.Frame(parent, bg=DANGER, height=0)
        self.starve_frame.pack(fill=tk.X, padx=20)
        self.starve_frame.pack_propagate(False)
        self.starve_label = tk.Label(self.starve_frame, text="", bg=DANGER, fg="white",
                                     font=("Helvetica",10,"bold"))
        self.starve_label.pack(pady=5)

        # ── Resizable 3-pane splitter (Gantt / Explainer / Metrics) ───────
        # PanedWindow lets the user drag dividers to resize each section
        paned = tk.PanedWindow(parent, orient=tk.VERTICAL,
                               bg=CARD_BG,           # divider colour
                               sashwidth=6,          # thickness of draggable divider
                               sashrelief=tk.FLAT,
                               sashpad=2,
                               opaqueresize=True)
        paned.pack(fill=tk.BOTH, expand=True, padx=20, pady=(4,8))

        # ── PANE 1: Gantt chart (largest, starts at ~55% height) ──────────
        gantt_pane = tk.Frame(paned, bg=BG_DARK)
        gantt_outer = tk.Frame(gantt_pane, bg=BG_DARK)
        gantt_outer.pack(fill=tk.BOTH, expand=True)
        self.gantt_scroll = tk.Scrollbar(gantt_outer, orient=tk.HORIZONTAL,
                                         bg=CARD_BG, troughcolor=CARD_BG)
        self.gantt_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        gantt_vscroll = tk.Scrollbar(gantt_outer, orient=tk.VERTICAL,
                                     bg=CARD_BG, troughcolor=CARD_BG)
        gantt_vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.gantt_canvas = tk.Canvas(gantt_outer, bg=PANEL_BG,
                                      highlightthickness=0,
                                      xscrollcommand=self.gantt_scroll.set,
                                      yscrollcommand=gantt_vscroll.set)
        self.gantt_canvas.pack(fill=tk.BOTH, expand=True)
        self.gantt_scroll.config(command=self.gantt_canvas.xview)
        gantt_vscroll.config(command=self.gantt_canvas.yview)
        # Mouse wheel scrolling on Gantt
        self.gantt_canvas.bind("<MouseWheel>",
            lambda e: self.gantt_canvas.yview_scroll(-1*(e.delta//120), "units"))
        paned.add(gantt_pane, minsize=120, stretch="always")

        # ── PANE 2: Step explainer (compact, starts at ~18% height) ───────
        explain_pane = tk.Frame(paned, bg="#0D1B2A")
        self.explain_frame = explain_pane   # keep same reference used elsewhere

        explain_top = tk.Frame(explain_pane, bg="#0D1B2A")
        explain_top.pack(fill=tk.X, padx=10, pady=(6,0))
        self.step_counter_label = tk.Label(explain_top, text="",
                                           bg="#252540", fg=INFO,
                                           font=("Helvetica",9,"bold"),
                                           padx=8, pady=2)
        self.step_counter_label.pack(side=tk.LEFT)
        self.ready_queue_label = tk.Label(explain_top, text="",
                                          bg="#1A1A2E", fg=TEXT_MUTED,
                                          font=("Helvetica",9))
        self.ready_queue_label.pack(side=tk.LEFT, padx=(10,0))

        self.explain_headline = tk.Label(explain_pane, text="",
                                         bg="#0D1B2A", fg=TEXT_PRIMARY,
                                         font=("Helvetica",11,"bold"),
                                         anchor=tk.W, wraplength=1100)
        self.explain_headline.pack(fill=tk.X, padx=10, pady=(4,1))

        self.explain_reason = tk.Label(explain_pane, text="",
                                       bg="#0D1B2A", fg=SUCCESS,
                                       font=("Helvetica",10),
                                       anchor=tk.W, wraplength=1100,
                                       justify=tk.LEFT)
        self.explain_reason.pack(fill=tk.X, padx=10, pady=(0,1))

        self.explain_detail = tk.Label(explain_pane, text="",
                                       bg="#0D1B2A", fg=TEXT_MUTED,
                                       font=("Helvetica",9),
                                       anchor=tk.W, wraplength=1100,
                                       justify=tk.LEFT)
        self.explain_detail.pack(fill=tk.X, padx=10, pady=(0,1))

        self.explain_tip = tk.Label(explain_pane, text="",
                                    bg="#0D1B2A", fg=WARNING,
                                    font=("Helvetica",9,"italic"),
                                    anchor=tk.W, wraplength=1100,
                                    justify=tk.LEFT)
        self.explain_tip.pack(fill=tk.X, padx=10, pady=(0,6))

        paned.add(explain_pane, minsize=60, stretch="never")

        # ── PANE 3: Metrics table + summary cards ─────────────────────────
        metrics_pane = tk.Frame(paned, bg=BG_DARK)

        tk.Label(metrics_pane, text="⊞  Process Metrics", bg=BG_DARK, fg=ACCENT,
                 font=("Helvetica",12,"bold")).pack(anchor=tk.W, padx=4, pady=(6,3))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Dark.Treeview", background=PANEL_BG, foreground=TEXT_PRIMARY,
                        fieldbackground=PANEL_BG, rowheight=26,
                        font=("Helvetica",10))
        style.configure("Dark.Treeview.Heading", background=CARD_BG,
                        foreground=TEXT_MUTED, font=("Helvetica",9,"bold"),
                        relief=tk.FLAT)
        style.map("Dark.Treeview", background=[("selected", ACCENT)],
                  foreground=[("selected","white")])

        table_frame = tk.Frame(metrics_pane, bg=PANEL_BG)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=(0,4))

        cols = ("PID","Burst","Arrival","Priority","Start","Finish",
                "Waiting","Turnaround","Response")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings",
                                 style="Dark.Treeview")
        for col, w in zip(cols, [60,60,70,70,60,65,70,90,80]):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor=tk.CENTER)
        vsb = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.pack(fill=tk.BOTH, expand=True)

        # Summary stat cards
        self.summary_frame = tk.Frame(metrics_pane, bg=BG_DARK)
        self.summary_frame.pack(fill=tk.X, pady=(2,4))
        self.summary_labels = {}
        self.ctx_label = None
        for key in ["Avg Wait","Avg Turnaround","CPU Util","Throughput","Ctx Switches"]:
            card = tk.Frame(self.summary_frame, bg=CARD_BG)
            card.pack(side=tk.LEFT, padx=4, ipadx=10, ipady=5)
            tk.Label(card, text=key, bg=CARD_BG, fg=TEXT_MUTED,
                     font=("Helvetica",8)).pack()
            val = tk.Label(card, text="—", bg=CARD_BG, fg=TEXT_PRIMARY,
                           font=("Helvetica",13,"bold"))
            val.pack()
            self.summary_labels[key] = val

        paned.add(metrics_pane, minsize=140, stretch="never")

        # Set initial sash positions after window renders
        # Gantt ~55%, Explainer ~18%, Metrics ~27%
        def _set_sash(event=None):
            h = paned.winfo_height()
            if h > 10:
                paned.sash_place(0, 0, int(h * 0.55))
                paned.sash_place(1, 0, int(h * 0.73))
                paned.unbind("<Configure>")
        paned.bind("<Configure>", _set_sash)

    # ═════════════════════════════════════════════════════════════════════════
    # TAB 2: COMPARISON
    # ═════════════════════════════════════════════════════════════════════════
    def _build_comparison_page(self, parent):
        hdr = tk.Frame(parent, bg=BG_DARK)
        hdr.pack(fill=tk.X, padx=20, pady=(16,8))
        tk.Label(hdr, text="⚖  Algorithm Comparison", bg=BG_DARK, fg=ACCENT,
                 font=("Helvetica",14,"bold")).pack(side=tk.LEFT)
        tk.Button(hdr, text="▶  Run All Algorithms", bg=SUCCESS, fg=BG_DARK,
                  relief=tk.FLAT, font=("Helvetica",11,"bold"), cursor="hand2",
                  command=self._run_comparison).pack(side=tk.RIGHT, ipady=6, ipadx=12)

        tk.Label(parent,
                 text="Runs your current process list through all 5 algorithms simultaneously and ranks them.",
                 bg=BG_DARK, fg=TEXT_MUTED, font=("Helvetica",10)).pack(anchor=tk.W, padx=20)

        # Winner banner
        self.winner_frame = tk.Frame(parent, bg=CARD_BG, height=0)
        self.winner_frame.pack(fill=tk.X, padx=20, pady=(10,0))
        self.winner_frame.pack_propagate(False)
        self.winner_label = tk.Label(self.winner_frame, text="", bg=CARD_BG,
                                     fg=WARNING, font=("Helvetica",12,"bold"))
        self.winner_label.pack(pady=8)

        # Comparison table
        cmp_frame = tk.Frame(parent, bg=PANEL_BG)
        cmp_frame.pack(fill=tk.X, padx=20, pady=(10,8))

        cmp_cols = ("Algorithm","Avg Wait","Avg Turnaround","CPU Util %",
                    "Throughput","Ctx Switches","Winner?")
        self.cmp_tree = ttk.Treeview(cmp_frame, columns=cmp_cols, show="headings",
                                     style="Dark.Treeview", height=6)
        widths = [160,85,120,90,90,105,80]
        for col, w in zip(cmp_cols, widths):
            self.cmp_tree.heading(col, text=col)
            self.cmp_tree.column(col, width=w, anchor=tk.CENTER)
        self.cmp_tree.pack(fill=tk.X, padx=2, pady=2)

        style = ttk.Style()
        style.configure("Winner.Treeview.Row", background="#1A2A1A")

        # Bar charts
        tk.Label(parent, text="⬛  Visual Comparison", bg=BG_DARK, fg=ACCENT,
                 font=("Helvetica",12,"bold")).pack(anchor=tk.W, padx=20, pady=(12,6))
        self.cmp_canvas = tk.Canvas(parent, bg=PANEL_BG, height=260,
                                    highlightthickness=0)
        self.cmp_canvas.pack(fill=tk.X, padx=20, pady=(0,16))

    def _run_comparison(self):
        if not self.processes:
            messagebox.showwarning("No Processes", "Add processes first.")
            return

        results = compare_all(self.processes, self.quantum_var.get())

        for row in self.cmp_tree.get_children():
            self.cmp_tree.delete(row)

        # Find winner for each metric
        best_wait  = min(results.values(), key=lambda r: r["avg_wait"])["avg_wait"]
        best_ta    = min(results.values(), key=lambda r: r["avg_ta"])["avg_ta"]
        best_util  = max(results.values(), key=lambda r: r["cpu_util"])["cpu_util"]

        # Rank by composite score (lower is better)
        def score(r):
            return r["avg_wait"] * 0.4 + r["avg_ta"] * 0.4 + (100 - r["cpu_util"]) * 0.2

        ranked = sorted(results.items(), key=lambda x: score(x[1]))
        winner_name = ranked[0][0]

        # Update winner banner
        self.winner_frame.config(height=44)
        self.winner_label.config(
            text=f"🏆  Best overall: {winner_name}  "
                 f"(Avg Wait: {results[winner_name]['avg_wait']:.1f}  |  "
                 f"Avg Turnaround: {results[winner_name]['avg_ta']:.1f})")

        for algo, r in ranked:
            is_winner = "🏆" if algo == winner_name else ""
            tag = "winner" if algo == winner_name else ""
            self.cmp_tree.insert("", tk.END, values=(
                algo,
                f"{r['avg_wait']:.2f}",
                f"{r['avg_ta']:.2f}",
                f"{r['cpu_util']:.1f}",
                f"{r['throughput']:.3f}",
                r['ctx_switches'],
                is_winner
            ), tags=(tag,))

        self.cmp_tree.tag_configure("winner", background="#1A2A1A", foreground=SUCCESS)

        # Draw bar charts
        self._draw_comparison_bars(results, winner_name)

    def _draw_comparison_bars(self, results, winner):
        c = self.cmp_canvas
        c.delete("all")
        if not results:
            return

        algos  = list(results.keys())
        colors = [PROCESS_COLORS[i % len(PROCESS_COLORS)] for i in range(len(algos))]
        W = 860
        charts = [
            ("Avg Waiting Time (lower=better)",   [r["avg_wait"]  for r in results.values()], False),
            ("Avg Turnaround (lower=better)",      [r["avg_ta"]    for r in results.values()], False),
            ("CPU Utilization % (higher=better)",  [r["cpu_util"]  for r in results.values()], True),
        ]

        chart_w = W // len(charts)
        bar_w   = max(18, chart_w // (len(algos) + 2))
        max_bar_h = 140

        for ci, (title, vals, higher_better) in enumerate(charts):
            ox = 20 + ci * chart_w
            oy = 200

            c.create_text(ox + chart_w//2, 18, text=title,
                          fill=TEXT_MUTED, font=("Helvetica",9), anchor=tk.CENTER)
            c.create_line(ox+10, oy, ox+chart_w-10, oy, fill=CARD_BG)

            max_val = max(vals) if max(vals) > 0 else 1
            best_val = max(vals) if higher_better else min(vals)

            for bi, (algo, val) in enumerate(zip(algos, vals)):
                bx = ox + 20 + bi * (bar_w + 6)
                bh = int((val / max_val) * max_bar_h)
                color = SUCCESS if val == best_val else colors[bi]
                c.create_rectangle(bx, oy - bh, bx + bar_w, oy,
                                   fill=color, outline="")
                c.create_text(bx + bar_w//2, oy - bh - 8,
                              text=f"{val:.1f}", fill=TEXT_PRIMARY,
                              font=("Helvetica",8))
                c.create_text(bx + bar_w//2, oy + 12,
                              text=algo[:5], fill=TEXT_MUTED,
                              font=("Helvetica",8), angle=0)

        # Legend
        for i, (algo, color) in enumerate(zip(algos, colors)):
            lx = 20 + i * 140
            c.create_rectangle(lx, 230, lx+12, 242, fill=color, outline="")
            c.create_text(lx+16, 236, text=algo, fill=TEXT_MUTED,
                          font=("Helvetica",9), anchor=tk.W)

    # ═════════════════════════════════════════════════════════════════════════
    # TAB 3: SYNCHRONIZATION
    # ═════════════════════════════════════════════════════════════════════════
    def _build_sync_page(self, parent):
        # Selector row
        sel_row = tk.Frame(parent, bg=BG_DARK)
        sel_row.pack(fill=tk.X, padx=20, pady=(16,8))

        tk.Label(sel_row, text="🔒  Synchronization Demo", bg=BG_DARK,
                 fg=ACCENT, font=("Helvetica",12,"bold")).pack(side=tk.LEFT)

        self.sync_var = tk.StringVar(value="Mutex Lock")
        sync_options = ["Mutex Lock", "Producer / Consumer", "Deadlock", "Race Condition"]
        sync_menu = ttk.OptionMenu(sel_row, self.sync_var, "Mutex Lock", *sync_options,
                                   command=self._on_sync_change)
        sync_menu.pack(side=tk.LEFT, padx=10)

        tk.Button(sel_row, text="▶  Start Demo", bg=ACCENT, fg="white",
                  relief=tk.FLAT, font=("Helvetica",11,"bold"), cursor="hand2",
                  command=self._start_sync_demo).pack(side=tk.LEFT, padx=8,
                                                       ipady=5, ipadx=10)
        tk.Button(sel_row, text="⏮ Reset", bg=CARD_BG, fg=TEXT_MUTED,
                  relief=tk.FLAT, font=("Helvetica",10), cursor="hand2",
                  command=self._reset_sync).pack(side=tk.LEFT, ipady=5, ipadx=8)

        tk.Label(sel_row, text="Speed:", bg=BG_DARK, fg=TEXT_MUTED,
                 font=("Helvetica",10)).pack(side=tk.LEFT, padx=(12,4))
        self.sync_speed = tk.IntVar(value=5)
        tk.Scale(sel_row, variable=self.sync_speed, from_=1, to=10,
                 orient=tk.HORIZONTAL, bg=BG_DARK, fg=TEXT_MUTED,
                 troughcolor=CARD_BG, highlightthickness=0,
                 showvalue=False, length=80).pack(side=tk.LEFT)

        # Concept explanation card
        self.concept_frame = tk.Frame(parent, bg=CARD_BG)
        self.concept_frame.pack(fill=tk.X, padx=20, pady=(0,8))
        self.concept_label = tk.Label(self.concept_frame, text="",
                                      bg=CARD_BG, fg=INFO,
                                      font=("Helvetica",10), wraplength=900,
                                      justify=tk.LEFT)
        self.concept_label.pack(anchor=tk.W, padx=12, pady=8)

        # Visual canvas (threads + resources)
        self.sync_canvas = tk.Canvas(parent, bg=PANEL_BG, height=220,
                                     highlightthickness=0)
        self.sync_canvas.pack(fill=tk.X, padx=20, pady=(0,6))

        # Buffer display (for producer/consumer)
        self.buffer_frame = tk.Frame(parent, bg=BG_DARK, height=0)
        self.buffer_frame.pack(fill=tk.X, padx=20)
        self.buffer_frame.pack_propagate(False)
        self.buffer_canvas = tk.Canvas(self.buffer_frame, bg=PANEL_BG,
                                       height=60, highlightthickness=0)
        self.buffer_canvas.pack(fill=tk.X)

        # Event log
        tk.Label(parent, text="📋  Event Log", bg=BG_DARK, fg=ACCENT,
                 font=("Helvetica",11,"bold")).pack(anchor=tk.W, padx=20, pady=(8,4))

        log_frame = tk.Frame(parent, bg=PANEL_BG)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0,16))

        self.sync_log = tk.Text(log_frame, bg=PANEL_BG, fg=TEXT_PRIMARY,
                                font=("Courier",10), relief=tk.FLAT,
                                state=tk.DISABLED, wrap=tk.WORD, height=8)
        log_scroll = tk.Scrollbar(log_frame, command=self.sync_log.yview,
                                  bg=CARD_BG, troughcolor=CARD_BG)
        self.sync_log.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.sync_log.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Text tags for colors
        self.sync_log.tag_configure("acquire",   foreground=SUCCESS)
        self.sync_log.tag_configure("release",   foreground=INFO)
        self.sync_log.tag_configure("blocked",   foreground=WARNING)
        self.sync_log.tag_configure("deadlock",  foreground=DANGER)
        self.sync_log.tag_configure("produce",   foreground="#BD93F9")
        self.sync_log.tag_configure("consume",   foreground="#FF79C6")
        self.sync_log.tag_configure("race",      foreground=WARNING)
        self.sync_log.tag_configure("wait",      foreground=TEXT_MUTED)
        self.sync_log.tag_configure("time",      foreground=TEXT_MUTED)

        self._on_sync_change("Mutex Lock")

    def _on_sync_change(self, val=None):
        name = self.sync_var.get()
        concepts = {
            "Mutex Lock":
                "Mutex (Mutual Exclusion): Only ONE thread can hold the lock at a time. "
                "Others block until it's released. Prevents race conditions in critical sections. "
                "Used in: file writes, database transactions, shared memory.",
            "Producer / Consumer":
                "Semaphore-based solution to the Bounded Buffer problem. "
                "Two semaphores: 'empty' (counts free slots) and 'full' (counts items). "
                "Producer waits when buffer is full. Consumer waits when buffer is empty. "
                "This is how OS I/O buffers, message queues, and pipes work.",
            "Deadlock":
                "Deadlock occurs when 4 Coffman conditions hold simultaneously: "
                "(1) Mutual exclusion  (2) Hold & wait  (3) No preemption  (4) Circular wait. "
                "Thread-A holds Lock-1 and wants Lock-2. Thread-B holds Lock-2 and wants Lock-1. "
                "Neither can proceed. OS must detect and recover by terminating one thread.",
            "Race Condition":
                "Race condition: two threads read-modify-write a shared variable without synchronization. "
                "Result depends on scheduling order → non-deterministic bugs. "
                "Fix: wrap critical section with a mutex so read+write is atomic.",
        }
        self.concept_label.config(text=concepts.get(name, ""))

    def _start_sync_demo(self):
        if self.sync_job:
            self.root.after_cancel(self.sync_job)
        self._reset_sync_visuals()

        name = self.sync_var.get()
        if name == "Mutex Lock":
            self.sync_events = simulate_mutex(num_threads=3, work_duration=3)
        elif name == "Producer / Consumer":
            self.sync_events = simulate_producer_consumer(buffer_size=5)
            self.buffer_frame.config(height=70)
        elif name == "Deadlock":
            self.sync_events = simulate_deadlock()
        else:
            self.sync_events = simulate_race_condition(steps=4)

        self.sync_frame = 0
        self.sync_playing = True
        self._animate_sync()

    def _reset_sync(self):
        if self.sync_job:
            self.root.after_cancel(self.sync_job)
        self.sync_playing = False
        self._reset_sync_visuals()

    def _reset_sync_visuals(self):
        self.sync_canvas.delete("all")
        self.buffer_canvas.delete("all")
        self.buffer_frame.config(height=0)
        self.sync_log.config(state=tk.NORMAL)
        self.sync_log.delete("1.0", tk.END)
        self.sync_log.config(state=tk.DISABLED)
        self.sync_frame = 0
        self.sync_events = []

    def _animate_sync(self):
        if not self.sync_playing:
            return
        if self.sync_frame >= len(self.sync_events):
            self.sync_playing = False
            return

        evt = self.sync_events[self.sync_frame]
        self._draw_sync_state(self.sync_frame)
        self._log_sync_event(evt)
        self.sync_frame += 1

        delay = int(660 - self.sync_speed.get() * 60)
        self.sync_job = self.root.after(delay, self._animate_sync)

    def _draw_sync_state(self, frame_idx):
        c = self.sync_canvas
        c.delete("all")
        events_so_far = self.sync_events[:frame_idx + 1]
        evt = self.sync_events[frame_idx]
        name = self.sync_var.get()

        if name == "Mutex Lock":
            self._draw_mutex_visual(c, events_so_far, evt)
        elif name == "Producer / Consumer":
            self._draw_prodcons_visual(c, events_so_far, evt)
        elif name == "Deadlock":
            self._draw_deadlock_visual(c, events_so_far, evt)
        else:
            self._draw_race_visual(c, events_so_far, evt)

    def _draw_mutex_visual(self, c, events, current_evt):
        threads = ["T0","T1","T2"]
        thread_x = [160, 400, 640]
        lock_x, lock_y = 400, 110

        # Determine lock state from event history
        holder = None
        blocked = set()
        for e in events:
            if e.event == EventType.ACQUIRE or e.event == EventType.UNBLOCKED:
                holder = e.thread
            elif e.event == EventType.RELEASE:
                holder = None
            elif e.event == EventType.BLOCKED:
                blocked.add(e.thread)
            elif e.event == EventType.UNBLOCKED:
                blocked.discard(e.thread)

        # Draw lock box
        lock_color = DANGER if holder else SUCCESS
        c.create_rectangle(lock_x-50, lock_y-24, lock_x+50, lock_y+24,
                           fill=lock_color, outline="white", width=2)
        c.create_text(lock_x, lock_y-8, text="MUTEX",
                      fill="white", font=("Helvetica",10,"bold"))
        c.create_text(lock_x, lock_y+10,
                      text=f"Held by: {holder}" if holder else "FREE",
                      fill="white", font=("Helvetica",9))

        # Draw threads
        for i, (tid, tx) in enumerate(zip(threads, thread_x)):
            if tid == holder:
                color, status = SUCCESS, "RUNNING"
                # Draw connection line to lock
                c.create_line(tx, 60, lock_x, lock_y-24,
                              fill=SUCCESS, width=2, dash=(4,2))
            elif tid in blocked:
                color, status = WARNING, "BLOCKED"
                c.create_line(tx, 60, lock_x, lock_y+24,
                              fill=WARNING, width=1, dash=(3,3))
            else:
                color, status = TEXT_MUTED, "WAITING"

            c.create_oval(tx-30, 30, tx+30, 90, fill=color, outline="white", width=1)
            c.create_text(tx, 60, text=tid, fill="white",
                          font=("Helvetica",11,"bold"))
            c.create_text(tx, 105, text=status, fill=color,
                          font=("Helvetica",9))

        # Current event banner
        c.create_rectangle(20, 150, 840, 178, fill=CARD_BG, outline="")
        color_map = {
            EventType.ACQUIRE: SUCCESS, EventType.RELEASE: INFO,
            EventType.BLOCKED: WARNING, EventType.UNBLOCKED: SUCCESS,
            EventType.WAIT: TEXT_MUTED,
        }
        evt_color = color_map.get(current_evt.event, TEXT_PRIMARY)
        c.create_text(430, 164, text=f"t={current_evt.time}  {current_evt.detail}",
                      fill=evt_color, font=("Helvetica",10), anchor=tk.CENTER)

    def _draw_prodcons_visual(self, c, events, current_evt):
        buffer_size = 5
        # Count current buffer level
        level = 0
        for e in events:
            if e.event == EventType.PRODUCE:
                level = e.value
            elif e.event == EventType.CONSUME:
                level = e.value

        # Draw producer
        prod_color = SUCCESS if current_evt.thread == "Producer" else TEXT_MUTED
        c.create_rectangle(40, 80, 140, 140, fill=prod_color, outline="white")
        c.create_text(90, 110, text="PRODUCER", fill="white",
                      font=("Helvetica",9,"bold"))

        # Draw buffer slots
        slot_w = 52
        buf_ox = 180
        for i in range(buffer_size):
            bx = buf_ox + i * (slot_w + 4)
            filled = i < level
            fill_color = "#BD93F9" if filled else CARD_BG
            c.create_rectangle(bx, 80, bx+slot_w, 140,
                               fill=fill_color, outline=TEXT_MUTED, width=1)
            if filled:
                c.create_text(bx+slot_w//2, 110, text="▪",
                              fill="white", font=("Helvetica",14))
        c.create_text(buf_ox + buffer_size*(slot_w+4)//2, 155,
                      text=f"Buffer: {level}/{buffer_size}",
                      fill=TEXT_MUTED, font=("Helvetica",10))

        # Draw consumer
        cons_color = "#FF79C6" if current_evt.thread == "Consumer" else TEXT_MUTED
        bx_end = buf_ox + buffer_size*(slot_w+4) + 10
        c.create_rectangle(bx_end, 80, bx_end+100, 140,
                           fill=cons_color, outline="white")
        c.create_text(bx_end+50, 110, text="CONSUMER",
                      fill="white", font=("Helvetica",9,"bold"))

        # Arrows
        c.create_line(140, 110, 180, 110, fill=SUCCESS, width=2,
                      arrow=tk.LAST)
        c.create_line(bx_end-6, 110, bx_end, 110, fill="#FF79C6", width=2,
                      arrow=tk.LAST)

        # Status bar
        c.create_rectangle(20, 175, 840, 200, fill=CARD_BG, outline="")
        wait_colors = {
            EventType.BUFFER_FULL: DANGER, EventType.BUFFER_EMPTY: DANGER,
            EventType.PRODUCE: "#BD93F9", EventType.CONSUME: "#FF79C6",
        }
        evt_color = wait_colors.get(current_evt.event, TEXT_PRIMARY)
        c.create_text(430, 188, text=f"t={current_evt.time}  {current_evt.detail}",
                      fill=evt_color, font=("Helvetica",10))

        # Update buffer strip canvas
        bc = self.buffer_canvas
        bc.delete("all")
        for i in range(buffer_size):
            bx = 20 + i * 58
            bc.create_rectangle(bx, 8, bx+50, 52,
                                fill="#BD93F9" if i < level else CARD_BG,
                                outline=TEXT_MUTED)
            bc.create_text(bx+25, 30, text=str(i+1),
                          fill="white" if i < level else TEXT_MUTED,
                          font=("Helvetica",10))

    def _draw_deadlock_visual(self, c, events, current_evt):
        # Thread circles
        positions = {"Thread-A": (160, 110), "Thread-B": (680, 110)}
        # Resource boxes
        resources  = {"Lock-1": (340, 60), "Lock-2": (500, 60)}
        holders    = {}
        blockers   = {}
        deadlocked = False

        for e in events:
            if e.event == EventType.ACQUIRE:
                holders[e.resource] = e.thread
            elif e.event == EventType.BLOCKED:
                blockers[e.thread] = e.resource
            elif e.event == EventType.DEADLOCK:
                deadlocked = True

        # Draw resources
        for rname, (rx, ry) in resources.items():
            holder = holders.get(rname)
            color = DANGER if holder else SUCCESS
            c.create_rectangle(rx-45, ry-20, rx+45, ry+20,
                               fill=color, outline="white", width=1)
            c.create_text(rx, ry-6, text=rname,
                          fill="white", font=("Helvetica",9,"bold"))
            c.create_text(rx, ry+8,
                          text=f"↳ {holder}" if holder else "free",
                          fill="white", font=("Helvetica",8))

        # Draw threads
        for tname, (tx, ty) in positions.items():
            color = DANGER if deadlocked else (SUCCESS if tname in holders.values() else TEXT_MUTED)
            c.create_oval(tx-40, ty-40, tx+40, ty+40,
                         fill=color, outline="white", width=2)
            c.create_text(tx, ty, text=tname.replace("Thread-","T"),
                         fill="white", font=("Helvetica",10,"bold"))

            # Draw blocking arrow
            if tname in blockers:
                wanted = blockers[tname]
                if wanted in resources:
                    rx, ry = resources[wanted]
                    c.create_line(tx + (40 if tx < rx else -40), ty,
                                  rx, ry + 20,
                                  fill=WARNING, width=2, dash=(5,3),
                                  arrow=tk.LAST)

        if deadlocked:
            c.create_rectangle(200, 165, 640, 195, fill=DANGER, outline="")
            c.create_text(420, 180,
                          text="☠  DEADLOCK DETECTED — Circular wait: A→Lock2→B→Lock1→A",
                          fill="white", font=("Helvetica",10,"bold"))
        else:
            c.create_rectangle(20, 165, 840, 190, fill=CARD_BG, outline="")
            c.create_text(430, 178, text=f"t={current_evt.time}  {current_evt.detail}",
                          fill=TEXT_PRIMARY, font=("Helvetica",10))

    def _draw_race_visual(self, c, events, current_evt):
        counter_val = current_evt.value
        expected = sum(1 for e in events
                       if e.event == EventType.RACE and "writes" in e.detail)

        # Two thread boxes
        for i, (tname, tx, color) in enumerate([
                ("Thread-A", 160, ACCENT), ("Thread-B", 640, "#FF79C6")]):
            active = current_evt.thread == tname
            border = "white" if active else TEXT_MUTED
            c.create_rectangle(tx-70, 60, tx+70, 140,
                               fill=color if active else CARD_BG,
                               outline=border, width=2 if active else 1)
            c.create_text(tx, 100, text=tname,
                         fill="white" if active else TEXT_MUTED,
                         font=("Helvetica",11,"bold"))

        # Shared counter box
        c.create_rectangle(340, 60, 500, 140, fill=CARD_BG,
                          outline=WARNING, width=2)
        c.create_text(420, 85, text="SHARED", fill=TEXT_MUTED,
                     font=("Helvetica",9))
        c.create_text(420, 108, text=f"counter = {counter_val}",
                     fill=WARNING, font=("Helvetica",13,"bold"))

        # Expected vs actual
        c.create_text(420, 155,
                      text=f"Expected: ~{expected*2} operations done  |  Actual: {counter_val}  |  Lost updates: {max(0, expected*2 - counter_val*2 + counter_val)}",
                      fill=DANGER, font=("Helvetica",9))

        # Status
        c.create_rectangle(20, 175, 840, 200, fill=CARD_BG, outline="")
        c.create_text(430, 188, text=f"t={current_evt.time}  {current_evt.detail}",
                     fill=WARNING, font=("Helvetica",10))

    def _log_sync_event(self, evt):
        tag_map = {
            EventType.ACQUIRE:      "acquire",
            EventType.RELEASE:      "release",
            EventType.BLOCKED:      "blocked",
            EventType.UNBLOCKED:    "acquire",
            EventType.PRODUCE:      "produce",
            EventType.CONSUME:      "consume",
            EventType.BUFFER_FULL:  "blocked",
            EventType.BUFFER_EMPTY: "blocked",
            EventType.DEADLOCK:     "deadlock",
            EventType.RACE:         "race",
            EventType.WAIT:         "wait",
        }
        self.sync_log.config(state=tk.NORMAL)
        tag = tag_map.get(evt.event, "wait")
        icon = {"acquire":"✅","release":"🔓","blocked":"⏳","deadlock":"☠",
                "produce":"📦","consume":"📤","race":"⚠","wait":"⚙"}.get(tag,"•")
        line = f"[t={evt.time:>3}]  {icon}  {evt.thread:<12} {evt.detail}\n"
        self.sync_log.insert(tk.END, line, tag)
        self.sync_log.see(tk.END)
        self.sync_log.config(state=tk.DISABLED)

    # ═════════════════════════════════════════════════════════════════════════
    # PROCESS MANAGEMENT
    # ═════════════════════════════════════════════════════════════════════════
    def _add_process(self):
        try:
            pid     = self.pid_entry.get().strip()
            burst   = int(self.burst_entry.get())
            arrival = int(self.arrival_entry.get())
            priority= int(self.priority_entry.get())
        except ValueError:
            messagebox.showerror("Input Error", "Burst, Arrival, Priority must be integers.")
            return
        if not pid:
            messagebox.showerror("Input Error", "PID cannot be empty.")
            return
        if any(p.pid == pid for p in self.processes):
            messagebox.showerror("Input Error", f"PID '{pid}' already exists.")
            return
        if burst <= 0:
            messagebox.showerror("Input Error", "Burst time must be > 0.")
            return

        color = PROCESS_COLORS[self.color_index % len(PROCESS_COLORS)]
        self.color_index += 1
        self.processes.append(Process(pid=pid, burst_time=burst,
                                      arrival_time=arrival, priority=priority,
                                      color=color))
        self._refresh_process_list()
        self.pid_entry.delete(0, tk.END)
        self.pid_entry.insert(0, "P" + str(len(self.processes)+1))

    # ═══════════════════════════════════════════════════════════════════════
    # SAVE / LOAD
    # ═══════════════════════════════════════════════════════════════════════
    # ═══════════════════════════════════════════════════════════════════════
    # PDF EXPORT
    # ═══════════════════════════════════════════════════════════════════════
    def _export_pdf(self):
        """
        Export the current simulation results to a PDF report.
        Requires a simulation to have been run first.
        The PDF contains:
          - Header with algorithm name, date, quantum
          - Input process table
          - Gantt chart (drawn as coloured rectangles)
          - Per-process metrics table
          - Summary stats (avg wait, turnaround, CPU util, throughput)
          - Algorithm explanation with pros/cons
        """
        if not self.scheduled_processes or not self.timeline:
            messagebox.showwarning(
                "No Results",
                "Please run a simulation first before exporting.\n\n"
                "Click 'Run Simulation', then export.")
            return

        # Build a smart default filename
        algo_slug = self.algo_var.get().replace(" ", "_").replace("+", "plus")
        default_name = f"scheduler_{algo_slug}_{len(self.processes)}procs.pdf"

        filepath = filedialog.asksaveasfilename(
            title="Export Simulation Report as PDF",
            defaultextension=".pdf",
            filetypes=[("PDF Document", "*.pdf"), ("All Files", "*.*")],
            initialfile=default_name
        )
        if not filepath:
            return

        # Show a progress indicator in the recent label
        self.recent_label.config(
            text="Generating PDF...", fg=WARNING)
        self.root.update_idletasks()

        success = export_pdf(
            filepath=filepath,
            processes=self.processes,
            scheduled=self.scheduled_processes,
            timeline=self.timeline,
            algo=self.algo_var.get(),
            quantum=self.quantum_var.get(),
            aging_log=self.aging_log if self.aging_log else [],
        )

        if success:
            filename = os.path.basename(filepath)
            size_kb  = os.path.getsize(filepath) // 1024
            self.recent_label.config(
                text=f"PDF saved: {filename}  ({size_kb} KB)",
                fg=SUCCESS)
            if hasattr(self, "status_msg"):
                self.status_msg.config(text=f"PDF exported: {filename}  ({size_kb} KB)")
            # Ask if they want to open it immediately
            if messagebox.askyesno(
                "PDF Exported",
                f"Report saved to:\n{filepath}\n\nOpen it now?"):
                os.startfile(filepath)   # Windows — opens with default PDF viewer
        else:
            self.recent_label.config(
                text="PDF export failed — check console.", fg=DANGER)
            messagebox.showerror(
                "Export Failed",
                "Could not generate the PDF.\n"
                "Make sure reportlab is installed:\n\n"
                "    pip install reportlab")


    def _save_processes(self):
        """
        Save current process list to a .json file.
        We store every field needed to fully recreate the process:
        pid, burst, arrival, priority, and color.
        The algorithm + quantum settings are also saved so the whole
        session can be restored exactly.
        """
        if not self.processes:
            messagebox.showwarning("Nothing to Save", "Add at least one process first.")
            return

        # Ask user where to save
        filepath = filedialog.asksaveasfilename(
            title="Save Process Set",
            defaultextension=".json",
            filetypes=[("Process Set JSON", "*.json"), ("All Files", "*.*")],
            initialfile="my_processes.json"
        )
        if not filepath:
            return  # User cancelled

        # Build the save data structure
        data = {
            "version": "2.0",
            "algorithm": self.algo_var.get(),
            "quantum": self.quantum_var.get(),
            "processes": [
                {
                    "pid":      p.pid,
                    "burst":    p.burst_time,
                    "arrival":  p.arrival_time,
                    "priority": p.priority,
                    "color":    p.color
                }
                for p in self.processes
            ]
        }

        try:
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)

            # Show filename in the recent label (just the name, not full path)
            filename = os.path.basename(filepath)
            self.recent_label.config(
                text=f"Saved: {filename}",
                fg="#50FA7B"
            )
            messagebox.showinfo("Saved",
                f"Saved {len(self.processes)} process(es) to:\n{filepath}")
            if hasattr(self, "status_msg"):
                self.status_msg.config(text=f"Saved: {os.path.basename(filepath)}")
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save file:\n{e}")

    def _load_processes(self):
        """
        Load a process set from a previously saved .json file.
        Restores processes, colors, algorithm selection, and quantum.
        Shows a preview of what will be loaded before replacing current data.
        """
        filepath = filedialog.askopenfilename(
            title="Load Process Set",
            filetypes=[("Process Set JSON", "*.json"), ("All Files", "*.*")]
        )
        if not filepath:
            return  # User cancelled

        try:
            with open(filepath, "r") as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showerror("Load Error", f"Could not read file:\n{e}")
            return

        # Validate file format
        if "processes" not in data:
            messagebox.showerror("Invalid File",
                "This file doesn't look like a saved process set.")
            return

        procs_data = data["processes"]
        if not procs_data:
            messagebox.showwarning("Empty File", "No processes found in this file.")
            return

        # Show a preview and ask for confirmation if there are existing processes
        if self.processes:
            names = ", ".join(p["pid"] for p in procs_data)
            preview = (
                f"Replace current {len(self.processes)} process(es)?\n\n"
                f"File has {len(procs_data)} process(es): {names}\n"
                f"Algorithm: {data.get('algorithm', 'FCFS')}  "
                f"Quantum: {data.get('quantum', 3)}"
            )
            answer = messagebox.askyesno("Load Process Set", preview)
            if not answer:
                return

        # Clear and reload
        self.processes.clear()
        self.color_index = 0

        for p_data in procs_data:
            # Use saved color if available, else assign a new one
            color = p_data.get("color",
                PROCESS_COLORS[self.color_index % len(PROCESS_COLORS)])
            self.color_index += 1

            self.processes.append(Process(
                pid=p_data["pid"],
                burst_time=p_data["burst"],
                arrival_time=p_data["arrival"],
                priority=p_data["priority"],
                color=color
            ))

        # Restore algorithm + quantum
        saved_algo = data.get("algorithm", "FCFS")
        if saved_algo in ["FCFS","SJF","SRTF","Round Robin","Priority","Priority + Aging"]:
            self.algo_var.set(saved_algo)
            self._on_algo_change()

        saved_quantum = data.get("quantum", 3)
        self.quantum_var.set(saved_quantum)

        # Refresh UI
        self._refresh_process_list()

        # Update the recent label
        filename = os.path.basename(filepath)
        self.recent_label.config(
            text=f"Loaded: {filename}  ({len(self.processes)} processes)",
            fg="#50FA7B"
        )

        # Clear any old gantt/metrics
        self.gantt_canvas.delete("all")
        self.timeline.clear()
        for row in self.tree.get_children():
            self.tree.delete(row)
        for k in self.summary_labels:
            self.summary_labels[k].config(text="—")
        self.time_label.config(text="")
        self._hide_starvation()

        # Update PID suggestion
        self.pid_entry.delete(0, tk.END)
        self.pid_entry.insert(0, "P" + str(len(self.processes) + 1))
        if hasattr(self, "status_msg"):
            self.status_msg.config(text=f"Loaded {len(self.processes)} processes  •  Algorithm: {self.algo_var.get()}")


    def _refresh_process_list(self):
        for w in self.proc_list_frame.winfo_children():
            w.destroy()
        for p in self.processes:
            # Outer row with left color accent
            row = tk.Frame(self.proc_list_frame, bg=CARD_BG)
            row.pack(fill=tk.X, pady=2)
            # Left color stripe
            tk.Frame(row, bg=p.color, width=4).pack(side=tk.LEFT, fill=tk.Y)
            # PID badge
            pid_lbl = tk.Label(row, text=p.pid, bg=CARD_BG, fg=p.color,
                               font=("Helvetica",10,"bold"), width=4)
            pid_lbl.pack(side=tk.LEFT, padx=(8,4), pady=6)
            # Stats
            tk.Label(row, text=f"B:{p.burst_time}  A:{p.arrival_time}  Pri:{p.priority}",
                     bg=CARD_BG, fg=TEXT_MUTED,
                     font=("Helvetica",9)).pack(side=tk.LEFT)
            def make_rm(proc):
                return lambda: self._remove_process(proc.pid)
            tk.Button(row, text="✕", bg=CARD_BG, fg=DANGER, relief=tk.FLAT,
                      font=("Helvetica",9), cursor="hand2",
                      command=make_rm(p)).pack(side=tk.RIGHT, padx=6)

    def _remove_process(self, pid):
        self.processes = [p for p in self.processes if p.pid != pid]
        self._refresh_process_list()

    def _add_sample_processes(self):
        samples = [("P1",6,0,2),("P2",4,1,1),("P3",8,2,3),("P4",3,3,1)]
        for pid, burst, arrival, priority in samples:
            color = PROCESS_COLORS[self.color_index % len(PROCESS_COLORS)]
            self.color_index += 1
            self.processes.append(
                Process(pid=pid, burst_time=burst, arrival_time=arrival,
                        priority=priority, color=color))
        self._refresh_process_list()

    def _clear_all(self):
        if self.animation_job:
            self.root.after_cancel(self.animation_job)
        self.processes.clear()
        self.timeline.clear()
        self.color_index = 0
        self._refresh_process_list()
        self.gantt_canvas.delete("all")
        for k in self.summary_labels:
            self.summary_labels[k].config(text="—")
        for row in self.tree.get_children():
            self.tree.delete(row)
        self.time_label.config(text="")
        self._hide_starvation()

    def _on_algo_change(self):
        is_rr = self.algo_var.get() == "Round Robin"
        self.quantum_spinbox.config(state=tk.NORMAL if is_rr else tk.DISABLED)

    # ═════════════════════════════════════════════════════════════════════════
    # SIMULATION + ANIMATION
    # ═════════════════════════════════════════════════════════════════════════
    # ═══════════════════════════════════════════════════════════════════════
    # STEP-BY-STEP EXPLAINER MODE
    # ═══════════════════════════════════════════════════════════════════════

    def _toggle_step_mode(self):
        """Switch between auto-play mode and manual step-by-step mode."""
        self.step_mode = not self.step_mode

        if self.step_mode:
            # Turn ON step mode
            self.step_btn.config(
                text="👣 Step Mode: ON",
                bg="#534AB7", fg="white")
            self.next_btn.config(state=tk.NORMAL)
            self.prev_btn.config(state=tk.NORMAL)
            self.play_btn.config(state=tk.DISABLED, text="▶ Play")
            # Stop any running animation
            if self.animation_job:
                self.root.after_cancel(self.animation_job)
                self.animation_job = None
            self.is_playing = False
            # Show explainer for current frame
            if self.timeline:
                self._show_explanation(self.current_frame)
        else:
            # Turn OFF step mode
            self.step_btn.config(
                text="👣 Step Mode: OFF",
                bg=CARD_BG, fg=TEXT_MUTED)
            self.next_btn.config(state=tk.DISABLED)
            self.prev_btn.config(state=tk.DISABLED)
            self.play_btn.config(state=tk.NORMAL)
            self._hide_explanation()

    def _next_step(self):
        """Advance one Gantt block forward and show its explanation."""
        if not self.timeline:
            return
        if self.current_frame < len(self.timeline):
            self._draw_gantt_frame(self.current_frame)
            self._show_explanation(self.current_frame)
            self.current_frame += 1
        else:
            # All done
            self._show_explanation(len(self.timeline))  # triggers done message
            self.next_btn.config(state=tk.DISABLED)

    def _prev_step(self):
        """Go back one Gantt block and re-show its explanation."""
        if not self.timeline:
            return
        if self.current_frame > 1:
            self.current_frame -= 1
            self._draw_gantt_frame(self.current_frame - 1)
            self._show_explanation(self.current_frame - 1)
            self.next_btn.config(state=tk.NORMAL)

    def _show_explanation(self, frame_idx):
        """Generate and display the explanation for a given timeline step."""
        if not self.timeline or not self.scheduled_processes:
            return

        exp = explain_step(
            step_index=frame_idx,
            timeline=self.timeline,
            all_processes=self.scheduled_processes,
            algo=self.algo_var.get(),
            quantum=self.quantum_var.get()
        )
        self.step_explanation = exp

        # Step counter badge
        total = len(self.timeline)
        current = min(frame_idx + 1, total)
        pid = exp.get("pid","")
        if pid == "DONE":
            badge_text = f"  COMPLETE — {total} steps  "
            badge_color = SUCCESS
        elif pid == "IDLE":
            badge_text = f"  Step {current} / {total}  —  CPU IDLE  "
            badge_color = TEXT_MUTED
        else:
            badge_text = f"  Step {current} / {total}  —  Running {pid}  "
            badge_color = INFO
        self.step_counter_label.config(text=badge_text, fg=badge_color)

        # Ready queue display
        rq = exp.get("ready_queue", [])
        if rq:
            rq_text = "Ready queue: " + " → ".join(rq)
        else:
            rq_text = "Ready queue: (empty)"
        self.ready_queue_label.config(text=rq_text)

        # Headline
        self.explain_headline.config(text=exp.get("headline", ""))

        # Reason (green — this is the KEY line students need to understand)
        self.explain_reason.config(text="Why: " + exp.get("reason", ""))

        # Detail (OS concept)
        detail = exp.get("detail","")
        self.explain_detail.config(
            text="Concept: " + detail if detail else "")

        # Tip (warning/observation — orange)
        tip = exp.get("tip")
        self.explain_tip.config(
            text="Note: " + tip if tip else "")

    def _hide_explanation(self):
        """Collapse the explainer panel."""
        for lbl in (self.explain_headline, self.explain_reason,
                    self.explain_detail, self.explain_tip,
                    self.step_counter_label, self.ready_queue_label):
            lbl.config(text="")


    def _run_simulation(self):
        if not self.processes:
            messagebox.showwarning("No Processes", "Add at least one process.")
            return
        if self.animation_job:
            self.root.after_cancel(self.animation_job)

        self.aging_log = []
        algo = self.algo_var.get()
        dispatch = {
            "FCFS":             lambda: fcfs(self.processes),
            "SJF":              lambda: sjf(self.processes),
            "SRTF":             lambda: srtf(self.processes),
            "Round Robin":      lambda: round_robin(self.processes, self.quantum_var.get()),
            "Priority":         lambda: priority_scheduling(self.processes),
            "Priority + Aging": lambda: self._run_aging(),
        }
        result = dispatch[algo]()
        if len(result) == 3:
            self.scheduled_processes, self.timeline, self.aging_log = result
        else:
            self.scheduled_processes, self.timeline = result

        # Show aging info bar
        if self.aging_log:
            self.aging_bar.config(height=36)
            self.aging_info_label.config(
                text=f"✅ Priority Aging applied {len(self.aging_log)} time(s) — "
                     f"boosted: {', '.join(set(x[1] for x in self.aging_log))}")
        else:
            self.aging_bar.config(height=0)

        self._reset_animation()
        self._populate_metrics()
        self._toggle_play()
        if hasattr(self, "status_msg"):
            self.status_msg.config(
                text=f"Running {self.algo_var.get()}  •  {len(self.processes)} processes  •  {len(self.timeline)} steps")

    def _run_aging(self):
        return priority_with_aging(self.processes, aging_interval=5)

    def _reset_animation(self):
        if self.animation_job:
            self.root.after_cancel(self.animation_job)
            self.animation_job = None
        self.is_playing = False
        self.current_frame = 0
        self.play_btn.config(text="▶ Play")
        self.gantt_canvas.delete("all")
        self._hide_starvation()
        self._hide_explanation()
        # Re-enable next/prev if step mode is on
        if self.step_mode and self.timeline:
            self.next_btn.config(state=tk.NORMAL)
            self.prev_btn.config(state=tk.NORMAL)
        if self.timeline:
            self._draw_gantt_frame(0)
            if self.step_mode:
                self._show_explanation(0)

    def _toggle_play(self):
        if not self.timeline:
            return
        self.is_playing = not self.is_playing
        self.play_btn.config(text="⏸ Pause" if self.is_playing else "▶ Play")
        if self.is_playing:
            self._animate()

    def _animate(self):
        if not self.is_playing:
            return
        if self.current_frame >= len(self.timeline):
            self.is_playing = False
            self.play_btn.config(text="▶ Play")
            self._check_starvation_end()
            return
        self._draw_gantt_frame(self.current_frame)
        self.current_frame += 1
        delay = int(660 - self.speed_var.get() * 60)
        self.animation_job = self.root.after(delay, self._animate)

    # ═════════════════════════════════════════════════════════════════════════
    # GANTT CHART
    # ═════════════════════════════════════════════════════════════════════════
    def _draw_gantt_frame(self, frame_idx):
        self.gantt_canvas.delete("all")
        if not self.timeline:
            return
        visible  = self.timeline[:frame_idx + 1]
        max_time = self.timeline[-1][2]
        scale    = max(20, min(55, 760 // max(max_time, 1)))

        row_map, row_colors = {}, {}
        row = 0
        for pid, s, e in self.timeline:
            if pid != "IDLE" and pid not in row_map:
                proc = next((p for p in self.processes if p.pid == pid), None)
                row_map[pid] = row
                row_colors[pid] = proc.color if proc else ACCENT
                row += 1

        canvas_h = (len(row_map) + 1) * (GANTT_HEIGHT + 8) + 70
        total_w  = max(900, max_time * scale + 160)
        self.gantt_canvas.config(
            scrollregion=(0, 0, total_w, canvas_h),
            height=canvas_h)

        ox = 82  # left margin

        # Row labels
        for pid, r in row_map.items():
            y = 28 + r*(GANTT_HEIGHT+8)
            color = row_colors.get(pid, ACCENT)
            self.gantt_canvas.create_rectangle(
                6, y, 76, y+GANTT_HEIGHT, fill=CARD_BG, outline=color, width=1)
            self.gantt_canvas.create_text(
                41, y+GANTT_HEIGHT//2, text=pid,
                fill=color, font=("Helvetica",10,"bold"))

        # Blocks
        for pid, start, end in visible:
            if pid == "IDLE":
                y_top = 28
                y_bot = 28+len(row_map)*(GANTT_HEIGHT+8)-8
                x1, x2 = ox+start*scale, ox+end*scale
                self.gantt_canvas.create_rectangle(
                    x1, y_top, x2, y_bot,
                    fill=IDLE_COLOR, outline="", stipple="gray50")
                self.gantt_canvas.create_text(
                    (x1+x2)//2, (y_top+y_bot)//2,
                    text="IDLE", fill=TEXT_MUTED, font=("Helvetica",8))
            else:
                r = row_map.get(pid, 0)
                color = row_colors.get(pid, ACCENT)
                y  = 28 + r*(GANTT_HEIGHT+8)
                x1 = ox + start*scale
                x2 = ox + end*scale
                self.gantt_canvas.create_rectangle(
                    x1, y, x2, y+GANTT_HEIGHT,
                    fill=color, outline=BG_DARK, width=1)
                if x2-x1 > 22:
                    self.gantt_canvas.create_text(
                        (x1+x2)//2, y+GANTT_HEIGHT//2,
                        text=str(end-start), fill=BG_DARK,
                        font=("Helvetica",8,"bold"))

        # Time axis
        ax_y = 28+len(row_map)*(GANTT_HEIGHT+8)+2
        self.gantt_canvas.create_line(
            ox, ax_y, ox+max_time*scale+10, ax_y,
            fill=TEXT_MUTED, width=1)
        tick_step = max(1, max_time//20)
        for t in range(0, max_time+1, tick_step):
            x = ox+t*scale
            self.gantt_canvas.create_line(x, ax_y, x, ax_y+5, fill=TEXT_MUTED)
            self.gantt_canvas.create_text(x, ax_y+13, text=str(t),
                                         fill=TEXT_MUTED, font=("Helvetica",7))

        # Playhead
        if frame_idx < len(self.timeline):
            px = ox + self.timeline[frame_idx][1]*scale
            self.gantt_canvas.create_line(
                px, 18, px, ax_y, fill=WARNING, width=2, dash=(4,2))
            self.gantt_canvas.create_text(
                px, 11, text=f"t={self.timeline[frame_idx][1]}",
                fill=WARNING, font=("Helvetica",8,"bold"))
            self.time_label.config(
                text=f"Current time: {self.timeline[frame_idx][1]}")

        # Context switch count
        ctx = sum(1 for i in range(1, len(visible))
                  if visible[i][0] != visible[i-1][0]
                  and visible[i][0] != "IDLE"
                  and visible[i-1][0] != "IDLE")
        self.summary_labels["Ctx Switches"].config(text=str(ctx))

        # Starvation check
        current_t = visible[-1][2]
        starving  = detect_starvation(
            self.scheduled_processes, current_t, STARVATION_THRESHOLD)
        if starving:
            self._show_starvation(starving)
        else:
            self._hide_starvation()

    # ═════════════════════════════════════════════════════════════════════════
    # METRICS
    # ═════════════════════════════════════════════════════════════════════════
    def _populate_metrics(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        total_time = self.timeline[-1][2] if self.timeline else 1
        idle = sum(e-s for pid,s,e in self.timeline if pid=="IDLE")
        cpu_util = (total_time-idle)/total_time*100
        tw = tt = 0
        for p in self.scheduled_processes:
            rt = p.response_time
            tag = "starve" if p.waiting_time >= STARVATION_THRESHOLD else ""
            self.tree.insert("", tk.END, values=(
                p.pid, p.burst_time, p.arrival_time, p.priority,
                p.start_time, p.finish_time,
                p.waiting_time, p.turnaround_time,
                rt if rt is not None else "—"
            ), tags=(tag,))
            tw += p.waiting_time
            tt += p.turnaround_time
        self.tree.tag_configure("starve", background="#3D1A1A", foreground=DANGER)
        n = len(self.scheduled_processes)
        if n:
            self.summary_labels["Avg Wait"].config(text=f"{tw/n:.1f}")
            self.summary_labels["Avg Turnaround"].config(text=f"{tt/n:.1f}")
            self.summary_labels["CPU Util"].config(text=f"{cpu_util:.1f}%")
            self.summary_labels["Throughput"].config(text=f"{n/total_time:.2f}")

    def _show_starvation(self, pids):
        self.starve_frame.config(height=34)
        self.starve_label.config(
            text=f"⚠  Starvation: {', '.join(pids)} waiting >{STARVATION_THRESHOLD} units. "
                 f"Real OS fix: priority aging.")

    def _hide_starvation(self):
        self.starve_frame.config(height=0)

    def _check_starvation_end(self):
        if self.scheduled_processes and self.timeline:
            s = detect_starvation(self.scheduled_processes,
                                  self.timeline[-1][2], STARVATION_THRESHOLD)
            if s:
                self._show_starvation(s)


if __name__ == "__main__":
    root = tk.Tk()
    app = CPUSchedulerApp(root)
    root.mainloop()
