# TUIKarma (2026) 🚀

> **Next-Gen Multi-Agent Orchestration & Evaluation Harness with Terminal UI**
> Built for Python 3.14+, Textual, Pydantic, Sandboxed Tools, and Trajectory Tracing.

---

## 🌟 Tính năng nổi bật

- **Workflow Engine (DAG & Vòng lặp Tự sửa lỗi / Self-Healing)**:
  - **Đồ thị luồng công việc linh hoạt (DAG & State Machine)**: Điều phối các bước theo nút (`AgentWorkflowNode`, `DecisionWorkflowNode`, `ToolWorkflowNode`, `ParallelWorkflowNode`, `HITLWorkflowNode`).
  - **Nhánh song song bất đồng bộ (Async Fork-Join DAG)**: Thực thi đồng thời nhiều Agent (`Coder` & `Tester`) qua `ParallelWorkflowNode` (`asyncio.gather`), sau đó hội tụ tại Gateway Join (`Critic`).
  - **Rẽ nhánh điều kiện động trong YAML (Dynamic Conditional Routing)**: Viết biểu thức logic bảo vệ (guard expressions) trực tiếp trên cạnh hoặc cổng quyết định (`contains(outputs.get('test'), 'FAIL')`, `iterations.get('code') < 2`).
  - **Cổng phê duyệt con người (Human-in-the-Loop Approval Gate)**: Nút `type: "hitl"` tạm dừng tiến trình chờ phê duyệt (`[A]` / `/approve` hoặc `/reject`), hỗ trợ đếm lùi timeout và chính sách auto-approve trong CI/CD headless.
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

# Chạy với Dynamic Routing & HITL Approval Gate Pipeline
.\.venv\Scripts\python.exe main.py --workflow tasks/pipelines/dynamic_hitl_pipeline.yaml --backend scenario

# Chạy offline / mock deterministic (không cần gateway)
.\.venv\Scripts\python.exe main.py --backend scenario
```

### 3. Khởi chạy Light Fluent 2 Mica Web UI Dashboard (Trình duyệt Web)
Trực quan hóa và điều khiển đàn Agent trên giao diện web hiện đại phong cách **Microsoft Fluent Design System 2** (Mica translucent material, Acrylic glassmorphism):
```powershell
.\.venv\Scripts\python.exe main.py --web --port 8080
```
Mở trình duyệt tại: `http://localhost:8080`
- **Project Workspace & AutoPilot Launcher**: Chuyển đổi giữa chế độ *Nhiệm vụ lẻ* và *Dự án dài hạn*. Hỗ trợ tạo dự án mới hoặc mở thư mục máy tính có sẵn bằng Folder Browser Modal.
- **Milestone Progress Tracker**: Theo dõi tiến độ từng cột mốc (M1, M2, M3...) với badge trạng thái động (Pending, In Progress, Completed).
- **Reflexion Memory Tab**: Xem các bài học kinh nghiệm mà AI tự đúc kết sau các lỗi và thành công để tránh lặp lại bug.
- **Visual DAG Canvas**: Xem trực quan luồng nodes, hiệu ứng pulse khi chạy, highlight cổng HITL và rollback.
- **Agent Matrix Cards**: Theo dõi trạng thái CoT, model routing của từng Agent trong Swarm.
- **HITL Command Ribbon**: Phê duyệt (`[A]`), Từ chối (`[D]`), Tạm dừng, Bước tiếp, Rollback hoặc nạp chỉ dẫn trực tiếp bằng chuột và phím tắt.
- **Workspace Code Viewer**: Duyệt cây tệp và xem mã nguồn dự án được sinh ra theo thời gian thực.

### 4. Vận hành Dự án Dài hạn với AutoPilot (Long-Running Autonomous Swarm)
Để giải quyết bài toán chạy các dự án phần mềm thực thụ kéo dài hàng giờ, nhiều ngày hoặc treo máy qua đêm:
1. **Phân rã Đa Cột mốc (Autonomous Planner)**: Thay vì dồn mọi thứ vào 1 lần chạy, hệ thống tự động phân tích mục tiêu và phân rã thành 3–5 Cột mốc (Milestones: M1 ➔ M2 ➔ M3) có tiêu chí nghiệm thu độc lập.
2. **Khảo sát Codebase có sẵn**: Khi mở thư mục dự án trên máy, hệ thống tự động scan cấu trúc, phát hiện file cấu hình chính (`pyproject.toml`, `package.json`,...) và kiểu tệp để nạp ngữ cảnh cho Agent.
3. **Reflexion Experience Memory**: Tự học và tích lũy tri thức sau mỗi lỗi cú pháp, race condition, concurrency vào `memory/experience_base.json` để đàn Agent tự điều chỉnh ở các cột mốc sau.
4. **Checkpoint & Saga Rollback**: Lưu trạng thái file trên đĩa sau mỗi milestone, bảo toàn tiến độ ngay cả khi tắt máy hoặc mạng gián đoạn.

#### Khởi chạy AutoPilot từ dòng lệnh:
```powershell
# Tạo dự án mới và tự hành hoàn toàn:
.\.venv\Scripts\python.exe main.py --autopilot "Xây dựng hệ thống Async LRU Cache có TTL và benchmark suite" --project-name "CacheEngine" --backend local

# Mở thư mục dự án có sẵn trên máy để tiếp tục phát triển / refactor:
.\.venv\Scripts\python.exe main.py --autopilot "Bổ sung test suite TDD và tối ưu xử lý ngoại lệ" --project-dir "C:\Users\...\MyProject" --backend local
```

### 5. Cách giao việc cho Swarm (3 phương thức linh hoạt)

#### 🔹 Cách A: Giao việc nhanh trực tiếp bằng dòng lệnh (`--prompt` hoặc `-p`)
Không cần tạo file, gõ trực tiếp yêu cầu từ Terminal:
```powershell
.\.venv\Scripts\python.exe main.py --prompt "Viết module Async Token Bucket Rate Limiter kèm test suite" --backend local
```

#### 🔹 Cách B: Giao việc bài bản bằng file cấu hình Task YAML (`--task`)
Tạo một file định nghĩa công việc (ví dụ `tasks/my_task.yaml`):
```yaml
id: "TASK-2026-002"
title: "Triển khai JWT Auth Middleware"
description: "Xây dựng middleware kiểm thực JWT bảo mật, xử lý token hết hạn, refresh token và unit test."
criteria:
  - name: "Code Correctness"
    weight: 0.5
  - name: "Test Coverage"
    weight: 0.3
  - name: "Security & Review"
    weight: 0.2
```
Khởi chạy kèm với workflow pipeline tự chọn:
```powershell
.\.venv\Scripts\python.exe main.py --task tasks/my_task.yaml --workflow tasks/pipelines/parallel_tdd_pipeline.yaml --backend local
```

#### 🔹 Cách C: Giao việc và can thiệp trực tiếp trong TUI / Web Dashboard
- **Trên Web Dashboard**: Nhập prompt vào form bên trái, chọn pipeline và nhấn `▶ Khởi chạy Swarm` hoặc chọn tab `🚀 Dự án & AutoPilot`.
- **Trên TUI**: Gõ vào ô input `⚡ HITL:` ở thanh đáy rồi nhấn `[Enter]`.

### 6. Khởi chạy Headless Benchmark (CI/CD hoặc Batch Testing)
```powershell
# Chạy benchmark tự động không cần mở giao diện TUI
.\.venv\Scripts\python.exe main.py --no-tui --workflow tasks/pipelines/dynamic_hitl_pipeline.yaml --backend scenario
```

### 7. Phát lại phiên làm việc đã lưu (Replay Mode)
```powershell
.\.venv\Scripts\python.exe main.py --replay traces/session_20261009_125925.jsonl
```

### 8. Chạy toàn bộ bộ kiểm thử tự động (42 Unit Tests & Full Stack Tests)
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
| **`[A]`** hoặc `/approve` | **Approve Tool / Gate** | Cấp phép chạy lệnh nguy hiểm hoặc phê duyệt HITL node |
| **`[D]`** hoặc `/reject` | **Reject Approval** | Từ chối phê duyệt HITL node |
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
│       ├── parallel_tdd_pipeline.yaml # Khai báo Declarative Fork-Join Parallel Pipeline
│       └── dynamic_hitl_pipeline.yaml # Khai báo Dynamic Conditional Routing & HITL Gate
├── sandbox_workspace/          # Không gian làm việc sandbox cô lập của Agents
├── traces/                     # Nhật ký lưu trữ session trajectory (.jsonl)
├── tests/
│   ├── test_harness.py         # Unit tests cho bus, agent, tools, evaluator, replay
│   ├── test_ui.py              # Textual pilot tests cho giao diện TUI & DAG widget
│   ├── test_workflow.py        # Unit tests cho DAGs, cycles, retries và saga rollback
│   ├── test_parallel_workflow.py # Unit tests cho Parallel Fork-Join DAG
│   ├── test_dynamic_routing_and_hitl.py # Unit tests cho Dynamic Expression Routing & HITL
│   ├── test_web_server.py      # Unit tests cho Light Fluent 2 Mica Web UI & REST/WS APIs
│   ├── test_autopilot_and_project.py # Unit tests cho Project Workspace & AutoPilot Engine
│   ├── test_sandbox_snapshot.py# Unit tests cho Snapshot & phục hồi file trên đĩa
│   ├── test_workflow_parser.py # Unit tests cho parser YAML pipeline
│   └── test_hitl_controls.py   # Unit tests cho các lệnh can thiệp HITL
├── projects/                   # Thư mục lưu trữ các Project Workspaces được quản lý
├── memory/                     # Cơ sở dữ liệu kinh nghiệm tích lũy (Reflexion Memory)
└── src/
    └── tuikarma/
        ├── core/
        │   ├── events.py       # Pydantic typed async events (Messages, Tools, HITL, Workflow)
        │   ├── event_bus.py    # Pub/Sub Async Event Bus với Subscribe & Unsubscribe
        │   ├── agent.py        # Agent state machine, dynamic model routing & reasoning loop
        │   ├── llm.py          # Universal LLM Gateway (OmniRoute Gateway & Scenario)
        │   └── topology.py     # Hybrid Swarm coordination & Workflow integration
        ├── project/
        │   └── manager.py      # Quản lý Project Workspace, scan codebase, browse thư mục
        ├── memory/
        │   └── reflexion.py    # Tích lũy tri thức, đúc kết kinh nghiệm & prompt injection
        ├── workflow/
        │   ├── state.py        # WorkflowState & NodeResult (Blackboard pattern)
        │   ├── node.py         # Agent, Decision, Tool, Parallel, và HITL Workflow Nodes
        │   ├── edge.py         # WorkflowEdge & Transition Guard Conditions
        │   ├── expression.py   # Safe Condition Expression Evaluator cho YAML
        │   ├── engine.py       # Core WorkflowEngine runner với Retry (3x30s) & Reverse Saga Rollback
        │   ├── parser.py       # Declarative YAML Workflow DSL Loader
        │   └── builder.py      # Pre-built self-healing coding workflows
        ├── web/
        │   ├── server.py       # FastAPI Web Dashboard server, WebSocket hub, REST endpoints
        │   └── static/
        │       ├── index.html  # Light Fluent 2 Mica semantic HTML5 layout
        │       ├── styles.css  # Microsoft Fluent 2 Mica material, Acrylic glass & animations
        │       └── app.js      # WebSocket realtime event client & DAG visualizer
        ├── tools/
        │   ├── base.py         # BaseTool & ToolRegistry
        │   ├── filesystem.py   # Sandboxed Read/Write/List file tools
        │   ├── runner.py       # Isolated Python/CLI execution tools với security gate
        │   └── snapshot.py     # SandboxSnapshotManager quản lý checkpoint/restore file đĩa
        ├── harness/
        │   ├── task.py         # TaskSpec & Evaluation criteria
        │   ├── planner.py      # Autonomous Project Planner phân rã 3-5 Milestones
        │   ├── autopilot.py    # AutoPilot Runner điều phối dự án dài hạn qua các cột mốc
        │   ├── evaluator.py    # Automated task evaluator & scoring engine
        │   └── trajectory.py   # JSONL recorder & replay engine
        └── ui/
            ├── styles.tcss     # Textual Cyber Dark styling
            ├── widgets/
            │   └── dag_view.py # Visual Workflow Pipeline DAG Widget
            └── app.py          # Ứng dụng TUI Textual đa bảng điều khiển với HITL bar
```

