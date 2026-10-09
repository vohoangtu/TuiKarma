# TUIKarma (2026) 🚀

> **Next-Gen Multi-Agent Orchestration & Evaluation Harness with Terminal UI**
> Built for Python 3.14+, Textual, Pydantic, Sandboxed Tools, and Trajectory Tracing.

---

## 🌟 Tính năng nổi bật

- **Workflow Engine (DAG & Vòng lặp Tự sửa lỗi / Self-Healing)**:
  - **Đồ thị luồng công việc linh hoạt (DAG & State Machine)**: Điều phối các bước theo nút (`AgentWorkflowNode`, `DecisionWorkflowNode`, `ToolWorkflowNode`, `ParallelWorkflowNode`).
  - **Nhánh song song bất đồng bộ (Async Fork-Join DAG)**: Thực thi đồng thời nhiều Agent (`Coder` & `Tester`) qua `ParallelWorkflowNode` (`asyncio.gather`), sau đó hội tụ tại Gateway Join (`Critic`).
  - **Vòng lặp phản hồi tự chữa lành (Self-Healing Loop)**: Tự động bắt lỗi kiểm thử từ Tester và chuyển tiếp về Coder để viết bản vá, kiểm tra lại cho tới khi đạt chuẩn nghiệm thu.
  - **Cơ chế Retry (3 lần x 30s) & Reverse Saga Rollback**: Tự động phục hồi snapshot file trên đĩa khi các bước thất bại.
  - **Blackboard State Management**: Chia sẻ ngữ cảnh giữa các bước qua đối tượng `WorkflowState`.
- **Kiến trúc Hybrid Swarm + Antigravity Gateway**:
  - 👑 **Supervisor**: (`antigravity/claude-sonnet-4-6`) Lập kế hoạch, phân rã mục tiêu và tổng hợp nghiệm thu.
  - 💻 **Coder**: (`antigravity/claude-sonnet-4-6`) Viết code, sinh bản vá và gọi công cụ tạo file.
  - 🧪 **Tester**: (`antigravity/gemini-3.1-flash-lite`) Thiết kế test suite, kiểm thử tự động.
  - 🔍 **Critic**: (`antigravity/claude-opus-4-6-thinking`) Đánh giá kiến trúc, bảo mật và chuẩn coding.
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

# Chạy với Declarative YAML Workflow Pipeline (Self-Healing)
.\.venv\Scripts\python.exe main.py --workflow tasks/pipelines/self_healing_coding.yaml --backend scenario

# Chạy với Parallel Fork-Join TDD Pipeline (Coder & Tester chạy song song)
.\.venv\Scripts\python.exe main.py --workflow tasks/pipelines/parallel_tdd_pipeline.yaml --backend scenario

# Chạy offline / mock deterministic (không cần gateway)
.\.venv\Scripts\python.exe main.py --backend scenario
```

### 3. Khởi chạy Headless Benchmark (CI/CD hoặc Batch Testing)
```powershell
# Chạy benchmark tự động với Live Antigravity Models hoặc YAML Pipeline
.\.venv\Scripts\python.exe main.py --no-tui --workflow tasks/pipelines/parallel_tdd_pipeline.yaml --backend scenario
```

### 4. Phát lại phiên làm việc đã lưu (Replay Mode)
```powershell
.\.venv\Scripts\python.exe main.py --replay traces/session_20261009_125925.jsonl
```

### 5. Chạy toàn bộ bộ kiểm thử tự động (23 Unit Tests & UI Pilot Tests)
```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

---

## ⌨️ Phím Tắt & Lệnh Điều Khiển HITL (Human-in-the-Loop)

| Phím / Lệnh | Ý nghĩa | Mô tả |
| :--- | :--- | :--- |
| **`[P]`** hoặc `/pause` | **Pause / Resume** | Tạm dừng/tiếp tục thực thi workflow của Swarm |
| **`[S]`** hoặc `/step` | **Step Forward** | Bước thủ công qua từng node/vòng lặp |
| **`[N]`** hoặc `/retry-now` | **Immediate Retry** | Hủy thời gian đếm lùi (30s) và retry node ngay lập tức |
| **`[K]`** hoặc `/skip` | **Skip Node** | Bỏ qua node bị lỗi hiện tại và chuyển tiếp node kế |
| **`[B]`** hoặc `/rollback` | **Force Rollback** | Dừng thử lại và kích hoạt quy trình bồi hoàn Saga lập tức |
| **`[A]`** hoặc `/approve` | **Approve Tool** | Cấp phép chạy lệnh nguy hiểm (Security Gate) |
| `/inject <chỉ dẫn>` | **Inject Guidance** | Nạp gợi ý sửa lỗi trực tiếp vào lần retry tiếp theo của Agent |

---

## 📁 Cấu trúc Thư mục

```text
TUIKarma/
├── pyproject.toml              # Cấu hình dự án & dependencies 2026
├── README.md
├── main.py                     # Entrypoint tiện lợi (CLI + TUI)
├── tasks/
│   ├── example_task.yaml       # Kịch bản benchmark mẫu
│   └── pipelines/
│       ├── self_healing_coding.yaml   # Khai báo Declarative DAG Workflow bằng YAML
│       └── parallel_tdd_pipeline.yaml # Khai báo Declarative Fork-Join Parallel Pipeline
├── sandbox_workspace/          # Không gian làm việc sandbox cô lập của Agents
├── traces/                     # Nhật ký lưu trữ session trajectory (.jsonl)
├── tests/
│   ├── test_harness.py         # Unit tests cho bus, agent, tools, evaluator, replay
│   ├── test_ui.py              # Textual pilot tests cho giao diện TUI & DAG widget
│   ├── test_workflow.py        # Unit tests cho DAGs, cycles, retries và saga rollback
│   ├── test_parallel_workflow.py # Unit tests cho ParallelFork-Join DAG
│   ├── test_sandbox_snapshot.py# Unit tests cho Snapshot & phục hồi file trên đĩa
│   ├── test_workflow_parser.py # Unit tests cho parser YAML pipeline
│   └── test_hitl_controls.py   # Unit tests cho các lệnh can thiệp HITL
└── src/
    └── tuikarma/
        ├── core/
        │   ├── events.py       # Pydantic typed async events (Messages, Tools, HITL, Workflow)
        │   ├── event_bus.py    # Pub/Sub Async Event Bus
        │   ├── agent.py        # Agent state machine, dynamic model routing & reasoning loop
        │   ├── llm.py          # Universal LLM Gateway (OmniRoute Gateway & Scenario)
        │   └── topology.py     # Hybrid Swarm coordination & Workflow integration
        ├── workflow/
        │   ├── state.py        # WorkflowState & NodeResult (Blackboard pattern)
        │   ├── node.py         # AgentWorkflowNode (model override), Decision, Tool nodes
        │   ├── edge.py         # WorkflowEdge & Transition Guard Conditions
        │   ├── engine.py       # Core WorkflowEngine runner với Retry (3x30s) & Reverse Saga Rollback
        │   ├── parser.py       # Declarative YAML Workflow DSL Loader
        │   └── builder.py      # Pre-built self-healing coding workflows
        ├── tools/
        │   ├── base.py         # BaseTool & ToolRegistry
        │   ├── filesystem.py   # Sandboxed Read/Write/List file tools
        │   ├── runner.py       # Isolated Python/CLI execution tools with security gate
        │   └── snapshot.py     # SandboxSnapshotManager quản lý checkpoint/restore file đĩa
        ├── harness/
        │   ├── task.py         # TaskSpec & Evaluation criteria
        │   ├── evaluator.py    # Automated task evaluator & scoring engine
        │   └── trajectory.py   # JSONL recorder & replay engine
        └── ui/
            ├── styles.tcss     # Textual Cyber Dark styling
            ├── widgets/
            │   └── dag_view.py # Visual Workflow Pipeline DAG Widget
            └── app.py          # Ứng dụng TUI Textual đa bảng điều khiển với HITL bar
```

