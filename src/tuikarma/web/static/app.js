/**
 * TUIKarma Light Fluent 2 Mica Web Dashboard Controller
 * Pure Vanilla JavaScript Client & WebSocket Realtime Event Engine
 */

class TUIKarmaWebClient {
  constructor() {
    this.ws = null;
    this.isPaused = false;
    this.currentPipeline = null;
    this.pipelines = [];
    this.currentPendingApproval = null;

    this.initElements();
    this.initEventListeners();
    this.initWebSocket();
    this.fetchPipelines();
    this.fetchSandboxFiles();
  }

  initElements() {
    // Header telemetry
    this.statusVal = document.getElementById("status-val");
    this.tokensVal = document.getElementById("tokens-val");
    this.costVal = document.getElementById("cost-val");
    this.scorePill = document.getElementById("score-pill");
    this.scoreVal = document.getElementById("score-val");
    this.wsIndicator = document.getElementById("ws-status-indicator");

    // Launch Form
    this.launchForm = document.getElementById("launch-form");
    this.taskPrompt = document.getElementById("task-prompt");
    this.pipelineSelect = document.getElementById("pipeline-select");
    this.backendSelect = document.getElementById("backend-select");
    this.btnLaunch = document.getElementById("btn-launch-task");

    // DAG Canvas
    this.dagFlow = document.getElementById("dag-flow");
    this.activePipelineName = document.getElementById("active-pipeline-name");
    this.activeStepInfo = document.getElementById("active-step-info");

    // HITL Ribbon
    this.hitlRibbon = document.getElementById("hitl-ribbon");
    this.hitlStatus = document.getElementById("hitl-ribbon-status");
    this.btnPause = document.getElementById("btn-pause");
    this.btnStep = document.getElementById("btn-step");
    this.btnApprove = document.getElementById("btn-approve");
    this.btnReject = document.getElementById("btn-reject");
    this.btnRetryNow = document.getElementById("btn-retry-now");
    this.btnSkip = document.getElementById("btn-skip");
    this.btnRollback = document.getElementById("btn-rollback");
    this.hitlInjectText = document.getElementById("hitl-inject-text");
    this.btnInjectSend = document.getElementById("btn-inject-send");

    // Stream tabs & contents
    this.dialogueList = document.getElementById("dialogue-list");
    this.terminalLog = document.getElementById("terminal-log");
    this.sandboxFileList = document.getElementById("sandbox-file-list");
    this.sandboxCodePreview = document.getElementById("sandbox-code-preview");
  }

  initEventListeners() {
    // Preset task buttons
    document.querySelectorAll(".preset-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const prompt = btn.getAttribute("data-prompt");
        if (prompt) {
          this.taskPrompt.value = prompt;
          this.taskPrompt.focus();
        }
      });
    });

    // Pipeline selection change -> update visual DAG preview
    this.pipelineSelect.addEventListener("change", () => {
      this.renderPipelinePreview(this.pipelineSelect.value);
    });

    // Form submission
    this.launchForm.addEventListener("submit", (e) => {
      e.preventDefault();
      this.handleLaunch();
    });

    // HITL Ribbon controls
    this.btnPause.addEventListener("click", () => this.togglePause());
    this.btnStep.addEventListener("click", () => this.sendHITLCommand("STEP"));
    this.btnApprove.addEventListener("click", () => this.sendHITLCommand("APPROVE"));
    this.btnReject.addEventListener("click", () => this.sendHITLCommand("REJECT"));
    this.btnRetryNow.addEventListener("click", () => this.sendHITLCommand("RETRY_NOW"));
    this.btnSkip.addEventListener("click", () => this.sendHITLCommand("SKIP"));
    this.btnRollback.addEventListener("click", () => this.sendHITLCommand("ROLLBACK"));

    this.btnInjectSend.addEventListener("click", () => {
      const guidance = this.hitlInjectText.value.trim();
      if (guidance) {
        this.sendHITLCommand("INJECT", guidance);
        this.hitlInjectText.value = "";
      }
    });

    // Global keyboard shortcuts for HITL
    document.addEventListener("keydown", (e) => {
      // Ignore if typing in text inputs
      if (["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) return;
      const key = e.key.toUpperCase();
      if (key === "P") this.togglePause();
      if (key === "S") this.sendHITLCommand("STEP");
      if (key === "A") this.sendHITLCommand("APPROVE");
      if (key === "D") this.sendHITLCommand("REJECT");
      if (key === "N") this.sendHITLCommand("RETRY_NOW");
      if (key === "K") this.sendHITLCommand("SKIP");
      if (key === "B") this.sendHITLCommand("ROLLBACK");
    });

    // Tabs switching
    document.querySelectorAll(".tab-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
        document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));
        btn.classList.add("active");
        const targetId = btn.getAttribute("data-tab");
        const targetEl = document.getElementById(targetId);
        if (targetEl) targetEl.classList.add("active");
        if (targetId === "tab-sandbox") this.fetchSandboxFiles();
      });
    });
  }

  initWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/api/ws`;
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      this.wsIndicator.style.background = "#107c41";
      this.appendTerminalLine("res", "[WebSocket] Đã kết nối với EventBus thời gian thực.");
    };

    this.ws.onclose = () => {
      this.wsIndicator.style.background = "#c42b1c";
      setTimeout(() => this.initWebSocket(), 2000); // Auto reconnect
    };

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        this.handleServerMessage(msg);
      } catch (err) {
        console.error("WS Parse error:", err);
      }
    };
  }

  handleServerMessage(msg) {
    if (msg.type === "INITIAL_STATE") {
      this.updateStatus(msg.data);
    } else if (msg.type === "EVENT") {
      this.processBusEvent(msg.event);
    } else if (msg.type === "TASK_FINISHED") {
      this.updateStatus(msg.data);
      this.btnLaunch.disabled = false;
      this.activeStepInfo.textContent = "Hoàn tất luồng công việc.";
      this.fetchSandboxFiles();
    }
  }

  processBusEvent(evt) {
    const type = evt._event_type;

    if (type === "MetricsEvent") {
      const curTokens = parseInt(this.tokensVal.textContent.split("/")[0]) || 0;
      const curOut = parseInt(this.tokensVal.textContent.split("/")[1]) || 0;
      const inT = curTokens + (evt.tokens_in || 0);
      const outT = curOut + (evt.tokens_out || 0);
      this.tokensVal.textContent = `${inT.toLocaleString()} / ${outT.toLocaleString()}`;
      const curCost = parseFloat(this.costVal.textContent.replace("$", "")) || 0;
      this.costVal.textContent = `$${(curCost + (evt.cost_usd || 0)).toFixed(4)}`;
    } else if (type === "StateChangeEvent") {
      this.updateAgentState(evt.agent_name, evt.new_state);
    } else if (type === "MessageEvent") {
      this.appendDialogue(evt.sender, evt.receiver, evt.content);
      this.updateAgentReasoning(evt.sender, evt.content);
    } else if (type === "ToolCallEvent") {
      this.appendTerminalLine("cmd", `[TOOL CALL] ${evt.agent_name} -> ${evt.tool_name}(${JSON.stringify(evt.arguments)})`);
    } else if (type === "ToolResultEvent") {
      const preview = (evt.result || "").substring(0, 160);
      this.appendTerminalLine("res", `[TOOL RESULT] ${evt.tool_name}: ${preview}...`);
      this.fetchSandboxFiles();
    } else if (type === "WorkflowStartedEvent") {
      this.statusVal.textContent = "RUNNING";
      this.activePipelineName.textContent = evt.workflow_name;
      this.activeStepInfo.textContent = `Bắt đầu DAG với ${evt.total_nodes} nodes...`;
      this.resetDAGNodesState();
    } else if (type === "WorkflowNodeStartedEvent") {
      this.setNodeActive(evt.node_id, "RUNNING");
      this.activeStepInfo.textContent = `Đang thực thi: ${evt.node_id} (${evt.agent_name || evt.node_type})`;
      if (evt.agent_name) this.updateAgentState(evt.agent_name, "THINKING");
    } else if (type === "WorkflowNodeCompletedEvent") {
      this.setNodeActive(evt.node_id, "SUCCESS");
    } else if (type === "WorkflowNodeRetryEvent") {
      this.setNodeActive(evt.node_id, "RETRYING", `${evt.attempt}/${evt.max_retries}`);
      this.activeStepInfo.textContent = `Nút ${evt.node_id} gặp sự cố, retry #${evt.attempt}...`;
    } else if (type === "WorkflowNodeRollbackEvent") {
      this.setNodeActive(evt.node_id, "ROLLBACK");
    } else if (type === "HITLApprovalRequestEvent") {
      this.currentPendingApproval = evt;
      this.setNodeActive(evt.node_id, "HITL");
      this.hitlRibbon.classList.add("waiting-approval");
      this.hitlStatus.innerHTML = `<span style="color:#d83b01;">✋ Yêu cầu duyệt [${evt.node_id}]:</span> ${evt.prompt}`;
    } else if (type === "HITLApprovalResponseEvent") {
      this.currentPendingApproval = null;
      this.hitlRibbon.classList.remove("waiting-approval");
      this.hitlStatus.textContent = "Điều khiển HITL:";
    } else if (type === "EvaluationResultEvent") {
      this.scorePill.style.display = "flex";
      this.scoreVal.textContent = `${(evt.score * 100).toFixed(1)}% (${evt.passed ? "PASS" : "FAIL"})`;
      this.scoreVal.style.color = evt.passed ? "var(--status-success)" : "var(--status-danger)";
    }
  }

  updateStatus(data) {
    if (!data) return;
    if (data.status) this.statusVal.textContent = data.status;
    if (data.tokens_in !== undefined && data.tokens_out !== undefined) {
      this.tokensVal.textContent = `${data.tokens_in.toLocaleString()} / ${data.tokens_out.toLocaleString()}`;
    }
    if (data.cost_usd !== undefined) {
      this.costVal.textContent = `$${data.cost_usd.toFixed(4)}`;
    }
    if (data.score !== null && data.score !== undefined) {
      this.scorePill.style.display = "flex";
      this.scoreVal.textContent = `${(data.score * 100).toFixed(1)}% (${data.passed ? "PASS" : "FAIL"})`;
    }
  }

  async fetchPipelines() {
    try {
      const res = await fetch("/api/pipelines");
      this.pipelines = await res.json();
      if (this.pipelines.length > 0) {
        this.pipelineSelect.innerHTML = "";
        this.pipelines.forEach((p) => {
          const opt = document.createElement("option");
          opt.value = p.path;
          opt.textContent = `${p.name} (${p.nodes.length} bước)`;
          this.pipelineSelect.appendChild(opt);
        });
        this.renderPipelinePreview(this.pipelineSelect.value);
      }
    } catch (err) {
      console.error("Fetch pipelines error:", err);
    }
  }

  renderPipelinePreview(selectedPath) {
    const p = this.pipelines.find((item) => item.path === selectedPath);
    if (!p) return;
    this.currentPipeline = p;
    this.activePipelineName.textContent = p.name;
    this.activeStepInfo.textContent = `Tổng cộng ${p.nodes.length} nodes trong DAG`;

    this.dagFlow.innerHTML = "";
    p.nodes.forEach((node, idx) => {
      const nodeEl = document.createElement("div");
      nodeEl.className = "dag-node";
      nodeEl.id = `dag-node-${node.id}`;
      nodeEl.innerHTML = `
        <div class="node-header">
          <span class="node-type-badge">${node.type || "AGENT"}</span>
        </div>
        <div class="node-title">${node.name || node.id}</div>
        <div class="node-agent">${node.agent ? `👑 ${node.agent}` : ""}</div>
      `;
      this.dagFlow.appendChild(nodeEl);

      if (idx < p.nodes.length - 1) {
        const arrow = document.createElement("div");
        arrow.className = "dag-arrow";
        arrow.textContent = "➔";
        this.dagFlow.appendChild(arrow);
      }
    });
  }

  resetDAGNodesState() {
    document.querySelectorAll(".dag-node").forEach((n) => {
      n.className = "dag-node";
    });
  }

  setNodeActive(nodeId, state, extra = "") {
    const el = document.getElementById(`dag-node-${nodeId}`);
    if (!el) return;
    el.className = "dag-node";
    if (state === "RUNNING") el.classList.add("active-running");
    if (state === "SUCCESS") el.classList.add("active-success");
    if (state === "HITL") el.classList.add("active-hitl");
    if (state === "ROLLBACK") el.classList.add("active-rollback");
    if (state === "RETRYING") {
      el.classList.add("active-fail");
      const title = el.querySelector(".node-title");
      if (title && extra) title.textContent += ` (Retry ${extra})`;
    }
  }

  updateAgentState(agentName, state) {
    const roleKey = (agentName || "").toLowerCase();
    const chip = document.getElementById(`chip-${roleKey}`);
    if (chip) {
      chip.className = `agent-status-chip ${state}`;
      chip.textContent = state;
    }
  }

  updateAgentReasoning(agentName, content) {
    const roleKey = (agentName || "").toLowerCase();
    const cot = document.getElementById(`cot-${roleKey}`);
    if (cot) {
      cot.textContent = content.substring(0, 100) + "...";
    }
  }

  appendDialogue(sender, receiver, text) {
    const item = document.createElement("div");
    item.className = "dialogue-item";
    const avatar = sender.includes("Supervisor") ? "👑" : sender.includes("Coder") ? "💻" : sender.includes("Tester") ? "🧪" : sender.includes("Critic") ? "🔍" : "👤";
    item.innerHTML = `
      <div class="dialogue-avatar">${avatar}</div>
      <div class="dialogue-bubble">
        <div class="dialogue-sender">${sender} ➔ ${receiver || "Swarm"}</div>
        <div>${this.escapeHTML(text)}</div>
      </div>
    `;
    this.dialogueList.appendChild(item);
    this.dialogueList.scrollTop = this.dialogueList.scrollHeight;
  }

  appendTerminalLine(type, text) {
    const line = document.createElement("div");
    line.className = `terminal-line ${type}`;
    line.textContent = text;
    this.terminalLog.appendChild(line);
    this.terminalLog.scrollTop = this.terminalLog.scrollHeight;
  }

  async fetchSandboxFiles() {
    try {
      const res = await fetch("/api/sandbox/files");
      const files = await res.json();
      this.sandboxFileList.innerHTML = "";
      if (files.length === 0) {
        this.sandboxFileList.innerHTML = `<div style="font-size: 0.8rem; color: var(--text-tertiary); padding: 6px;">Chưa có file nào sinh ra.</div>`;
        return;
      }
      files.forEach((f) => {
        const item = document.createElement("div");
        item.className = "file-item";
        item.innerHTML = `<span>📄</span> <span>${f.path}</span>`;
        item.addEventListener("click", () => this.viewSandboxFile(f.path, item));
        this.sandboxFileList.appendChild(item);
      });
      // Auto-preview first file
      if (files[0]) this.viewSandboxFile(files[0].path, this.sandboxFileList.firstElementChild);
    } catch (err) {
      console.error("Fetch sandbox files error:", err);
    }
  }

  async viewSandboxFile(path, el) {
    document.querySelectorAll(".file-item").forEach((i) => i.classList.remove("selected"));
    if (el) el.classList.add("selected");
    try {
      const res = await fetch(`/api/sandbox/file?path=${encodeURIComponent(path)}`);
      const data = await res.json();
      this.sandboxCodePreview.textContent = data.content || "(Tệp rỗng)";
    } catch (err) {
      this.sandboxCodePreview.textContent = `Lỗi đọc file: ${err}`;
    }
  }

  async handleLaunch() {
    const prompt = this.taskPrompt.value.trim();
    if (!prompt) return;

    this.btnLaunch.disabled = true;
    this.statusVal.textContent = "LAUNCHING";
    this.resetDAGNodesState();

    try {
      const res = await fetch("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: prompt,
          workflow_file: this.pipelineSelect.value,
          backend: this.backendSelect.value,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        alert(`Không thể khởi chạy: ${err.detail || "Lỗi không xác định"}`);
        this.btnLaunch.disabled = false;
      }
    } catch (err) {
      alert(`Lỗi kết nối máy chủ: ${err}`);
      this.btnLaunch.disabled = false;
    }
  }

  async sendHITLCommand(action, payload = null) {
    try {
      await fetch("/api/hitl/command", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: action, payload: payload }),
      });
    } catch (err) {
      console.error("Error sending HITL command:", err);
    }
  }

  togglePause() {
    this.isPaused = !this.isPaused;
    this.btnPause.textContent = this.isPaused ? "▶ Tiếp tục" : "⏸ Tạm dừng";
    this.sendHITLCommand(this.isPaused ? "PAUSE" : "RESUME");
  }

  escapeHTML(str) {
    return (str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
}

// Instantiate on DOM content loaded
document.addEventListener("DOMContentLoaded", () => {
  window.tuikarmaApp = new TUIKarmaWebClient();
});
