ReadyQueue — CPU Process Scheduler & Sync Visualizer
A desktop app that visualizes CPU scheduling algorithms and OS sync concepts in real time. Built with Python + tkinter from scratch.
Built with **Python** and **tkinter** — no web framework, no game engine, just pure Python.

---

## 📽️ Demo Video



**[▶ Watch Demo Video](YOUR_YOUTUBE_LINK_HERE)**

<!-- To add: upload a screen recording to YouTube, then replace YOUR_YOUTUBE_LINK_HERE with your video URL -->

---

## 📌 What Is This?

Most OS students learn scheduling algorithms by drawing Gantt charts by hand — slow and confusing. **ReadyQueue** fixes that.

You type in a list of processes, pick a scheduling algorithm, and press **Run**. The app:

- Draws an **animated Gantt chart** frame by frame
- Calculates **waiting time, turnaround time, CPU utilization** and more
- Explains **WHY** each scheduling decision was made, in plain English
- Shows **synchronization problems** like Deadlock and Race Condition — animated live
- Compares **all algorithms at once** and tells you which one performed best

---

## ✨ Features

### ⚡ Scheduler Tab
| Feature | Description |
|--------|-------------|
| 6 Scheduling Algorithms | FCFS, SJF, SRTF, Round Robin, Priority, Priority + Aging |
| Animated Gantt Chart | Live frame-by-frame animation with playhead |
| Step-by-Step Explainer | Explains WHY each process was picked at every step |
| Starvation Detection | Red warning banner when a process waits too long |
| Process Metrics Table | Waiting time, turnaround, response time per process |
| Summary Cards | Avg wait, CPU utilization, throughput, context switches |
| Priority Aging | Automatically boosts waiting processes to prevent starvation |

### ⚖️ Comparison Tab
| Feature | Description |
|--------|-------------|
| Run All Algorithms | Runs all 5 algorithms on your processes simultaneously |
| Winner Detection | 🏆 Trophy marks the best-performing algorithm |
| Bar Charts | Visual comparison of wait time, turnaround, CPU utilization |

### 🔒 Synchronization Tab
| Feature | Description |
|--------|-------------|
| Mutex Lock Demo | 3 threads competing for a shared lock — animated |
| Producer / Consumer | Bounded buffer with semaphores — fills and empties live |
| Deadlock Demo | Circular wait forming and detected in real time |
| Race Condition Demo | Lost updates from unsynchronized threads |
| Event Log | Colour-coded log of every sync event with timestamps |

### 💾 Global Features
| Feature | Description |
|--------|-------------|
| Save & Load | Save process sets to `.json` and reload anytime |
| Export PDF | One-click professional PDF report with Gantt chart + metrics |
| Resizable Layout | Drag dividers to resize Gantt, Explainer, and Metrics panels |
| Live Clock | Updates every second in the top bar |
| Status Bar | Shows what the app is doing at all times |
| Dark Theme | Deep navy + electric cyan branded interface |

---

## 🖼️ Screenshots

<!-- Add screenshots after taking them from your app -->
<!-- Drag and drop images into this section on GitHub, or use the format below -->

```
Screenshot 1 — Gantt Chart (FCFS)
Screenshot 2 — Comparison Tab
Screenshot 3 — Deadlock Demo
Screenshot 4 — PDF Export
```

<!-- Example format once you have images:
![Gantt Chart](screenshots/gantt.png)
![Comparison](screenshots/comparison.png)
-->

---

## 🧠 OS Concepts Covered

This project demonstrates the following Operating System concepts:

- CPU Scheduling (FCFS, SJF, SRTF, Round Robin, Priority)
- Gantt Charts, Burst Time, Arrival Time, Priority
- Waiting Time, Turnaround Time, Response Time
- Preemptive vs Non-Preemptive Scheduling
- Context Switching, CPU Utilization, Throughput
- Starvation and Priority Aging
- Convoy Effect, Time Quantum
- Mutex Lock, Semaphore, Bounded Buffer
- Deadlock and Coffman Conditions
- Race Condition and Critical Section
- Process Control Block (PCB)

---

## 📁 Project Structure

```
ReadyQueue/
│
├── main.py          # Main app — all UI, animation, and tkinter code
├── process.py       # Process data model (like a real OS PCB)
├── scheduler.py     # All 6 scheduling algorithm implementations
├── sync_demo.py     # Mutex, semaphore, deadlock, race condition simulations
├── explainer.py     # Generates plain-English step explanations
├── pdf_export.py    # Builds the PDF report using reportlab
└── README.md        # This file
```

---

## 🚀 How to Run

### Step 1 — Make sure Python is installed

Open **Command Prompt** and type:

```bash
python --version
```

You should see something like `Python 3.x.x`. If not, download Python from [python.org](https://python.org/downloads) — make sure to check **"Add Python to PATH"** during install.

---

### Step 2 — Download the project

Click the green **Code** button on this page → **Download ZIP** → Extract the folder anywhere on your PC.

Or if you have Git:

```bash
git clone https://github.com/YOUR_USERNAME/ReadyQueue.git
cd ReadyQueue
```

---

### Step 3 — Install the PDF library (one time only)

```bash
pip install reportlab
```

That's the only thing you need to install. Everything else is built into Python.

---

### Step 4 — Run the app

```bash
python main.py
```

The **ReadyQueue** window will open maximized with 4 sample processes already loaded.

Click **▶ RUN SIMULATION** to see it in action immediately.

---

## 🎮 Quick Start Guide

Once the app is open:

1. **Add processes** using the left panel — enter PID, Burst Time, Arrival Time, Priority
2. **Select an algorithm** from the radio buttons (start with FCFS)
3. **Click ▶ RUN SIMULATION**
4. Watch the **Gantt chart** animate
5. Read the **metrics table** below for waiting times and turnaround times
6. Try **👣 Step Mode** to understand each scheduling decision one step at a time
7. Go to the **Comparison tab** and click **Run All Algorithms** to see which is best
8. Go to the **Synchronization tab** and try the **Deadlock** demo
9. Click **📄 Export PDF Report** to save a full report

---

## ⚠️ Troubleshooting

| Problem | Fix |
|---------|-----|
| `python` not recognized | Use `python3 main.py` instead, or reinstall Python with "Add to PATH" checked |
| `ModuleNotFoundError: reportlab` | Run `pip install reportlab` in Command Prompt |
| `ModuleNotFoundError: explainer` | Make sure all 6 `.py` files are in the same folder |
| `ModuleNotFoundError: pdf_export` | Same as above — all files must be together |
| Window doesn't open | Run from Command Prompt, not by double-clicking the file |
| PDF opens blank | Run the simulation first before clicking Export |

---

## 🛠️ Built With

- **Python 3.14**
- **tkinter** — built-in Python GUI library
- **tkinter.ttk** — for the metrics table
- **reportlab** — for PDF generation
- **json** — for save/load functionality

No frameworks. No installs beyond reportlab. Just Python.

---

## 📚 Algorithms Explained

| Algorithm | Type | Key Idea | Main Problem |
|-----------|------|----------|--------------|
| FCFS | Non-preemptive | First arrived = first served | Convoy effect |
| SJF | Non-preemptive | Shortest burst runs next | Starvation of long jobs |
| SRTF | Preemptive | Shortest *remaining* time wins | High context switches |
| Round Robin | Preemptive | Everyone gets equal time slices | Performance depends on quantum size |
| Priority | Non-preemptive | Lowest priority number runs first | Starvation |
| Priority + Aging | Non-preemptive | Priority but waiting processes get boosted | More complex |

---

## 👤 Author

**Mashrafe Bin Morshed**
- Course: CSE323 — Operating Systems
- Section: 02
- ID: 2321889042

---

## 📄 License

This project is for educational purposes.
Feel free to use it, learn from it, and modify it.

---

## ⭐ If this helped you

Give it a **star** on GitHub — it helps others find it too!

```
Built with Python 🐍 | Designed for OS students 🎓 | Made from scratch by a beginner 💪
```
