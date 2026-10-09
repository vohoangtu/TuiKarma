# TUIKarma (2026) 🚀

> **Next-Gen Multi-Agent Orchestration & Evaluation Harness with Terminal UI**
> Built for Python 3.14+, Textual, Pydantic, Sandboxed Tools, and Trajectory Tracing.

---

## 🌟 Tính năng nổi bật

- **Kiến trúc Hybrid Hierarchical + Blackboard**: Phối hợp linh hoạt giữa các agent chuyên trách:
  - 👑 **Supervisor**: Lập kế hoạch, phân rã mục tiêu và tổng hợp nghiệm thu.
  - 💻 **Coder**: Viết code, sinh bản vá và gọi công cụ tạo file.
  - 🧪 **Tester**: Thiết kế test suite, kiểm thử tự động.
  - 🔍 **Critic**: Đánh giá kiến trúc, bảo mật và chuẩn coding.
- **TUI Dashboard thời gian thực (Textual)**:
  - **Agent Matrix**: Theo dõi trạng thái động (IDLE, THINKING, CALLING_TOOL, COMPLETED).
  - **Live Dialogue & CoT Stream**: Phân màu theo vai trò, hiển thị luồng suy nghĩ (Chain-of-Thought).
  - **Tool Inspector**: Giám sát lệnh, tham số và kết quả chạy công cụ trong sandbox.
  - **Harness Telemetry**: Đo lường tổng số token tiêu thụ, chi phí ước tính ($), độ trễ và điểm số benchmark.
- **Human-in-the-Loop (HITL) Toàn diện**:
  - **Interactive Command Bar**: Nhập phản hồi hoặc chỉ thị trực tiếp từ bàn phím gửi đến Agent Swarm.
  - **Security Gate & Approval**: Kiểm soát các lệnh nguy hiểm trước khi cho phép chạy (`[A]` Duyệt / `/deny`).
  - Phím tắt điều khiển: `P` (Pause/Resume), `S` (Step-by-Step debug), `R` (Restart), `Q` (Quit).
- **Automated Evaluation & Benchmarking**:
  - Nạp kịch bản từ file YAML (`tasks/example_task.yaml`).
  - Tự động chấm điểm (Score 0-100%) theo ma trận tiêu chí trọng số (Code Correctness, Test Coverage, Security).
- **Session Trajectory Recording & Replay (.jsonl)**:
  - Tự động ghi lại toàn bộ trajectory vào file JSONL trong thư mục `traces/`.
  - Khả năng phát lại nguyên vẹn phiên làm việc trong TUI với cờ `--replay`.

---

## 🛠 Cài đặt & Khởi chạy

### 1. Kích hoạt môi trường ảo (Đã tạo sẵn với Python 3.14+)
```powershell
.\.venv\Scripts\Activate.ps1
```

### 2. Khởi chạy TUI Harness (Chế độ tương tác thời gian thực)
Tự động kết nối tới **Antigravity Gateway** (`http://localhost:20128/v1`):
```powershell
.\.venv\Scripts\python.exe main.py
```
Hoặc ép dùng backend cụ thể:
```powershell
# Chạy với Antigravity Local Gateway (http://localhost:20128/v1)
.\.venv\Scripts\python.exe main.py --backend local

# Chạy offline / mock deterministic (không cần gateway)
.\.venv\Scripts\python.exe main.py --backend scenario
```

### 3. Khởi chạy Headless Benchmark (CI/CD hoặc Batch Testing)
```powershell
# Chạy benchmark tự động với Live Antigravity Models
.\.venv\Scripts\python.exe main.py --no-tui --backend local
```

### 4. Phát lại phiên làm việc đã lưu (Replay Mode)
```powershell
.\.venv\Scripts\python.exe main.py --replay traces/session_20261009_114807.jsonl
```

### 5. Chạy bộ kiểm thử tự động (Unit Tests & UI Pilot Tests)
```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

---

## 📁 Cấu trúc Thư mục

```text
TUIKarma/
├── pyproject.toml              # Cấu hình dự án & dependencies 2026
├── README.md
├── main.py                     # Entrypoint tiện lợi (CLI + TUI)
├── tasks/
│   └── example_task.yaml       # Kịch bản benchmark mẫu
├── sandbox_workspace/          # Không gian làm việc sandbox cô lập của Agents
├── traces/                     # Nhật ký lưu trữ session trajectory (.jsonl)
├── tests/
│   ├── test_harness.py         # Unit tests cho bus, agent, tools, evaluator, replay
│   └── test_ui.py              # Textual pilot tests cho giao diện TUI
└── src/
    └── tuikarma/
        ├── core/
        │   ├── events.py       # Pydantic typed async events (Messages, Tools, HITL, Eval)
        │   ├── event_bus.py    # Pub/Sub Async Event Bus
        │   ├── agent.py        # Agent state machine & reasoning loop
        │   ├── llm.py          # Universal LLM Gateway (Scenario, Mock & Live API)
        │   └── topology.py     # Hybrid Hierarchical Swarm coordination
        ├── tools/
        │   ├── base.py         # BaseTool & ToolRegistry
        │   ├── filesystem.py   # Sandboxed Read/Write/List file tools
        │   └── runner.py       # Isolated Python/CLI execution tools with security gate
        ├── harness/
        │   ├── task.py         # TaskSpec & Evaluation criteria
        │   ├── evaluator.py    # Automated task evaluator & scoring engine
        │   └── trajectory.py   # JSONL recorder & replay engine
        └── ui/
            ├── styles.tcss     # Textual Cyber Dark styling
            └── app.py          # Ứng dụng TUI Textual đa bảng điều khiển với HITL bar
```
