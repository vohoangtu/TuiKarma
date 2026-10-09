/**
 * TUIKarma Light Fluent 2 Mica Web Dashboard Controller
 * Microsoft Fluent 2 Mica Material UI & Autonomous AutoPilot Swarm Client
 */

class TUIKarmaWebClient {
  constructor() {
    this.ws = null;
    this.isPaused = false;
    this.currentPipeline = null;
    this.pipelines = [];
    this.currentPendingApproval = null;
    this.projects = [];
    this.activeProject = null;
    this.currentBrowserPathVal = null;
    this.parentBrowserPathVal = null;
    this.lessons = [];

    this.initElements();
    this.initEventListeners();
    this.initWebSocket();
    this.fetchPipelines();
    this.fetchSandboxFiles();
    this.fetchProjects();
    this.fetchLessons();
  }

  initElements() {
    // Header telemetry
    this.statusVal = document.getElementById("status-val");
    this.tokensVal = document.getElementById("tokens-val");
    this.costVal = document.getElementById("cost-val");
    this.scorePill = document.getElementById("score-pill");
    this.scoreVal = document.getElementById("score-val");
    this.wsIndicator = document.getElementById("ws-status-indicator");

    // Sidebar mode toggles & panels
    this.tabModeTask = document.getElementById("tab-mode-task");
    this.tabModeProject = document.getElementById("tab-mode-project");
    this.panelTaskRunner = document.getElementById("panel-task-runner");
    this.panelProjectAutopilot = document.getElementById("panel-project-autopilot");

    // Launch Form (Single Task)
    this.launchForm = document.getElementById("launch-form");
    this.taskPrompt = document.getElementById("task-prompt");
    this.pipelineSelect = document.getElementById("pipeline-select");
    this.backendSelect = document.getElementById("backend-select");
    this.btnLaunch = document.getElementById("btn-launch-task");

    // Project Workspace & AutoPilot
    this.recentProjectsSelect = document.getElementById("recent-projects-select");
    this.btnSubNew = document.getElementById("btn-sub-new");
    this.btnSubOpen = document.getElementById("btn-sub-open");
    this.newProjectForm = document.getElementById("new-project-form");
    this.openProjectForm = document.getElementById("open-project-form");
    this.newProjName = document.getElementById("new-proj-name");
    this.newProjGoal = document.getElementById("new-proj-goal");
    this.newProjDir = document.getElementById("new-proj-dir");
    this.openProjPath = document.getElementById("open-proj-path");
    this.openProjGoal = document.getElementById("open-proj-goal");
    this.btnOpenBrowserModal = document.getElementById("btn-open-browser-modal");
    this.btnScanCodebase = document.getElementById("btn-scan-codebase");
    this.codebaseSummaryBox = document.getElementById("codebase-summary-box");

    // Milestone Ribbon
    this.milestoneRibbon = document.getElementById("milestone-ribbon");
    this.activeProjectTitle = document.getElementById("active-project-title");
    this.activeProjectPathBadge = document.getElementById("active-project-path-badge");
    this.milestoneProgressBadge = document.getElementById("milestone-progress-badge");
    this.milestonesSteps = document.getElementById("milestones-steps");

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
    this.lessonsGrid = document.getElementById("lessons-grid");
    this.btnRefreshLessons = document.getElementById("btn-refresh-lessons");

    // Code Knowledge Graph (Graphify) Tab
    this.graphNodesCount = document.getElementById("graph-nodes-count");
    this.graphEdgesCount = document.getElementById("graph-edges-count");
    this.graphGodsCount = document.getElementById("graph-gods-count");
    this.graphCyclesCount = document.getElementById("graph-cycles-count");
    this.graphSymbolInput = document.getElementById("graph-symbol-input");
    this.btnGraphQuery = document.getElementById("btn-graph-query");
    this.btnGraphImpact = document.getElementById("btn-graph-impact");
    this.graphQueryResult = document.getElementById("graph-query-result");
    this.graphGodNodesList = document.getElementById("graph-god-nodes-list");
    this.btnRefreshGraph = document.getElementById("btn-refresh-graph");
    this.btnOpenGraphVisualizer = document.getElementById("btn-open-graph-visualizer");

    // Folder Browser Modal
    this.folderBrowserModal = document.getElementById("folder-browser-modal");
    this.currentBrowserPath = document.getElementById("current-browser-path");
    this.browserFolderList = document.getElementById("browser-folder-list");
    this.btnFolderUp = document.getElementById("btn-folder-up");
    this.btnCloseBrowser = document.getElementById("btn-close-browser");
    this.btnCancelBrowser = document.getElementById("btn-cancel-browser");
    this.btnSelectFolder = document.getElementById("btn-select-folder");
  }

  initEventListeners() {
    // Mode Switcher: Single Task vs Project AutoPilot
    if (this.tabModeTask && this.tabModeProject) {
      this.tabModeTask.addEventListener("click", () => {
        this.tabModeTask.classList.add("active");
        this.tabModeProject.classList.remove("active");
        this.panelTaskRunner.style.display = "block";
        this.panelProjectAutopilot.style.display = "none";
      });

      this.tabModeProject.addEventListener("click", () => {
        this.tabModeProject.classList.add("active");
        this.tabModeTask.classList.remove("active");
        this.panelTaskRunner.style.display = "none";
        this.panelProjectAutopilot.style.display = "block";
      });
    }

    // Sub-toggle: New Project vs Open Existing
    if (this.btnSubNew && this.btnSubOpen) {
      this.btnSubNew.addEventListener("click", () => {
        this.btnSubNew.classList.add("active");
        this.btnSubOpen.classList.remove("active");
        this.newProjectForm.style.display = "flex";
        this.openProjectForm.style.display = "none";
      });

      this.btnSubOpen.addEventListener("click", () => {
        this.btnSubOpen.classList.add("active");
        this.btnSubNew.classList.remove("active");
        this.openProjectForm.style.display = "flex";
        this.newProjectForm.style.display = "none";
      });
    }

    // Recent Projects Selector
    if (this.recentProjectsSelect) {
      this.recentProjectsSelect.addEventListener("change", () => {
        const projId = this.recentProjectsSelect.value;
        const proj = this.projects.find((p) => p.id === projId);
        if (proj) {
          this.activeProject = proj;
          this.renderMilestonesRibbon(proj);
          this.openProjPath.value = proj.path;
          this.openProjGoal.value = proj.goal || "";
          this.btnSubOpen.click();
          this.fetchSandboxFiles();
        }
      });
    }

    // New Project Form Submit -> AutoPilot Start
    if (this.newProjectForm) {
      this.newProjectForm.addEventListener("submit", (e) => {
        e.preventDefault();
        this.handleStartNewProjectAutoPilot();
      });
    }

    // Open Project Form Submit -> AutoPilot Start
    if (this.openProjectForm) {
      this.openProjectForm.addEventListener("submit", (e) => {
        e.preventDefault();
        this.handleStartOpenProjectAutoPilot();
      });
    }

    // Scan Codebase Button
    if (this.btnScanCodebase) {
      this.btnScanCodebase.addEventListener("click", () => this.handleScanCodebase());
    }

    // Folder Browser Modal Actions
    if (this.btnOpenBrowserModal) {
      this.btnOpenBrowserModal.addEventListener("click", () => {
        const initialPath = this.openProjPath.value.trim() || null;
        this.openFolderBrowser(initialPath);
      });
    }
    if (this.btnCloseBrowser) {
      this.btnCloseBrowser.addEventListener("click", () => {
        this.folderBrowserModal.style.display = "none";
      });
    }
    if (this.btnCancelBrowser) {
      this.btnCancelBrowser.addEventListener("click", () => {
        this.folderBrowserModal.style.display = "none";
      });
    }
    if (this.btnFolderUp) {
      this.btnFolderUp.addEventListener("click", () => {
        if (this.parentBrowserPathVal) {
          this.openFolderBrowser(this.parentBrowserPathVal);
        }
      });
    }
    if (this.btnSelectFolder) {
      this.btnSelectFolder.addEventListener("click", () => {
        if (this.currentBrowserPathVal) {
          this.openProjPath.value = this.currentBrowserPathVal;
          this.folderBrowserModal.style.display = "none";
          this.handleScanCodebase();
        }
      });
    }

    // Refresh Lessons Button
    if (this.btnRefreshLessons) {
      this.btnRefreshLessons.addEventListener("click", () => this.fetchLessons());
    }

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

    // Single Task Form submission
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
        if (targetId === "tab-memory") this.fetchLessons();
        if (targetId === "tab-graph") this.fetchGraphSummary();
      });
    });

    // Graphify Tab Action Buttons
    if (this.btnRefreshGraph) {
      this.btnRefreshGraph.addEventListener("click", () => this.fetchGraphSummary());
    }
    if (this.btnGraphQuery) {
      this.btnGraphQuery.addEventListener("click", () => this.handleGraphQuery());
    }
    if (this.btnGraphImpact) {
      this.btnGraphImpact.addEventListener("click", () => this.handleGraphImpact());
    }
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
      setTimeout(() => this.initWebSocket(), 2500); // Auto reconnect
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
    if (msg.type === "INITIAL_STATE" || msg.type === "STATUS_UPDATE") {
      this.updateStatus(msg.data);
    } else if (msg.type === "EVENT") {
      this.processBusEvent(msg.event);
    } else if (msg.type === "TASK_FINISHED") {
      this.updateStatus(msg.data);
      this.btnLaunch.disabled = false;
      this.activeStepInfo.textContent = "Hoàn tất luồng công việc.";
      this.fetchSandboxFiles();
      this.fetchProjects();
      this.fetchLessons();
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
      // Ensure DAG canvas nodes are rendered
      const pipe = this.pipelines.find(p => p.name === evt.workflow_name || (evt.workflow_name && p.path.includes("parallel_tdd")));
      if (pipe) {
        this.renderPipelinePreview(pipe.path);
      }
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
    if (data.active_project) {
      this.activeProject = data.active_project;
      this.renderMilestonesRibbon(data.active_project);
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
      cot.textContent = content.substring(0, 110) + "...";
    }
  }

  appendDialogue(sender, receiver, text) {
    const item = document.createElement("div");
    item.className = "dialogue-item";
    const avatar = sender.includes("Supervisor") ? "👑" : sender.includes("Coder") ? "💻" : sender.includes("Tester") ? "🧪" : sender.includes("Critic") ? "🔍" : sender.includes("AutoPilot") ? "🧭" : "👤";
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
        this.sandboxFileList.innerHTML = `<div style="font-size: 0.8rem; color: var(--text-tertiary); padding: 6px;">Chưa có file nào trong không gian làm việc.</div>`;
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

  /* ========================================================================
     Project Workspace & AutoPilot Engine Handlers
     ======================================================================== */

  async fetchProjects() {
    try {
      const res = await fetch("/api/projects");
      this.projects = await res.json();
      if (this.recentProjectsSelect) {
        this.recentProjectsSelect.innerHTML = `<option value="">-- Chọn dự án để tiếp tục --</option>`;
        this.projects.forEach((p) => {
          const opt = document.createElement("option");
          opt.value = p.id;
          opt.textContent = `${p.name} (${p.status}) - ${p.milestones ? p.milestones.length : 0} cột mốc`;
          this.recentProjectsSelect.appendChild(opt);
        });
      }
    } catch (err) {
      console.error("Fetch projects error:", err);
    }
  }

  renderMilestonesRibbon(project) {
    if (!project || !this.milestoneRibbon) return;
    this.milestoneRibbon.style.display = "block";
    this.activeProjectTitle.textContent = `Dự án: ${project.name}`;
    this.activeProjectPathBadge.textContent = project.path;

    const milestones = project.milestones || [];
    const completed = milestones.filter((m) => m.status === "COMPLETED").length;
    this.milestoneProgressBadge.textContent = `${completed}/${milestones.length} Milestones`;

    this.milestonesSteps.innerHTML = "";
    if (milestones.length === 0) {
      this.milestonesSteps.innerHTML = `<div style="font-size: 0.78rem; color: var(--text-tertiary); padding: 6px;">Đang chuẩn bị phân rã cột mốc...</div>`;
      return;
    }

    milestones.forEach((m) => {
      const card = document.createElement("div");
      card.className = `milestone-card ${m.status || "PENDING"}`;
      const statusIcon = m.status === "COMPLETED" ? "✔" : m.status === "IN_PROGRESS" ? "▶" : m.status === "FAILED" ? "✖" : "○";
      card.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span class="milestone-id-badge">${m.id}</span>
          <span style="font-size: 0.72rem; font-weight: 600;">${statusIcon} ${m.status}</span>
        </div>
        <div class="milestone-title">${this.escapeHTML(m.title)}</div>
        <div class="milestone-goal" title="${this.escapeHTML(m.goal)}">${this.escapeHTML(m.goal)}</div>
      `;
      this.milestonesSteps.appendChild(card);
    });
  }

  async handleStartNewProjectAutoPilot() {
    const name = this.newProjName.value.trim();
    const goal = this.newProjGoal.value.trim();
    const targetDir = this.newProjDir.value.trim() || null;
    if (!name || !goal) return;

    this.statusVal.textContent = "PLANNING";
    this.appendTerminalLine("cmd", `[AUTOPILOT] Khởi tạo dự án mới '${name}' với mục tiêu: ${goal}`);

    try {
      const res = await fetch("/api/autopilot/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name,
          goal: goal,
          target_dir: targetDir,
          backend: this.backendSelect ? this.backendSelect.value : "auto",
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        alert(`Không thể bắt đầu AutoPilot: ${err.detail || "Lỗi máy chủ"}`);
        return;
      }
      const data = await res.json();
      this.appendTerminalLine("res", `[AUTOPILOT] Đã kích hoạt AutoPilot cho ID: ${data.project_id}`);
      this.fetchProjects();
    } catch (err) {
      alert(`Lỗi kết nối AutoPilot: ${err}`);
    }
  }

  async handleStartOpenProjectAutoPilot() {
    const folderPath = this.openProjPath.value.trim();
    const goal = this.openProjGoal.value.trim();
    if (!folderPath) {
      alert("Vui lòng nhập hoặc chọn đường dẫn thư mục dự án.");
      return;
    }

    this.statusVal.textContent = "PLANNING";
    this.appendTerminalLine("cmd", `[GIAO VIỆC] Mở dự án tại '${folderPath}', nhận mục tiêu: ${goal}`);

    // Show milestone ribbon immediately with progress indicator
    if (this.milestoneRibbon) {
      this.milestoneRibbon.style.display = "block";
      const pName = folderPath.replace(/\\/g, "/").split("/").filter(Boolean).pop() || "Dự án";
      this.activeProjectTitle.textContent = `Dự án: ${pName}`;
      this.activeProjectPathBadge.textContent = folderPath;
      this.milestoneProgressBadge.textContent = "Đang khởi tạo...";
      this.milestonesSteps.innerHTML = `
        <div class="milestone-card IN_PROGRESS" style="width: 100%;">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <span class="milestone-id-badge">PLANNING</span>
            <span style="font-size: 0.72rem; font-weight: 600;">⌛ Đang phân tích</span>
          </div>
          <div class="milestone-title">Khảo sát Codebase & Lập kế hoạch Cột mốc</div>
          <div class="milestone-goal">AI Planner đang khảo sát toàn bộ codebase và phân rã mục tiêu: "${this.escapeHTML(goal)}"</div>
        </div>
      `;
    }

    // Auto-switch to Live Dialogue & CoT tab so user sees real-time progress
    const tabDialogueBtn = document.querySelector('.tab-btn[data-tab="tab-dialogue"]');
    if (tabDialogueBtn) tabDialogueBtn.click();

    // Auto-render default pipeline preview on DAG Canvas
    if (this.pipelines && this.pipelines.length > 0) {
      const p = this.pipelines.find(item => item.path.includes("parallel_tdd")) || this.pipelines[0];
      if (p) this.renderPipelinePreview(p.path);
    }

    try {
      const res = await fetch("/api/autopilot/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_path: folderPath,
          goal: goal || "Phát triển và bảo trì codebase",
          backend: this.backendSelect ? this.backendSelect.value : "auto",
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        alert(`Không thể bắt đầu thực thi: ${err.detail || "Lỗi máy chủ"}`);
        return;
      }
      const data = await res.json();
      this.appendTerminalLine("res", `[GIAO VIỆC] Đã nhận nhiệm vụ và bắt đầu thực thi trên codebase: ${data.project_path}`);
      if (data.project) {
        this.renderMilestonesRibbon(data.project);
      }
      this.fetchProjects();
    } catch (err) {
      alert(`Lỗi kết nối máy chủ: ${err}`);
    }
  }

  async handleScanCodebase() {
    const folderPath = this.openProjPath.value.trim();
    if (!folderPath) {
      alert("Vui lòng chọn thư mục cần quét.");
      return;
    }

    this.btnScanCodebase.disabled = true;
    this.btnScanCodebase.textContent = "⌛ Đang khảo sát Codebase...";

    try {
      const res = await fetch("/api/projects/open", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ folder_path: folderPath, goal: this.openProjGoal.value.trim() }),
      });

      if (!res.ok) {
        const err = await res.json();
        alert(`Lỗi khảo sát: ${err.detail}`);
        this.btnScanCodebase.disabled = false;
        this.btnScanCodebase.textContent = "🔍 Quét & Khảo sát Codebase này";
        return;
      }

      const data = await res.json();
      const cb = data.codebase;
      this.codebaseSummaryBox.style.display = "block";
      this.codebaseSummaryBox.innerHTML = `
        <div style="font-weight: 600; color: var(--accent-primary); margin-bottom: 4px;">📊 Kết quả khảo sát Codebase:</div>
        <div>• <strong>Tổng số tệp:</strong> ${cb.total_files} files</div>
        <div>• <strong>File cấu hình chính:</strong> ${cb.key_configs.length > 0 ? cb.key_configs.join(", ") : "Chưa có"}</div>
        <div>• <strong>Ngôn ngữ/Đuôi mở rộng:</strong> ${Object.entries(cb.file_types || {}).map(([k, v]) => `${k} (${v})`).join(", ")}</div>
      `;
      this.appendTerminalLine("res", `[SCAN CODEBASE] Tìm thấy ${cb.total_files} files trong thư mục '${cb.project_name}'.`);
      this.fetchSandboxFiles();
    } catch (err) {
      alert(`Lỗi scan: ${err}`);
    } finally {
      this.btnScanCodebase.disabled = false;
      this.btnScanCodebase.textContent = "🔍 Quét & Khảo sát Codebase này";
    }
  }

  async openFolderBrowser(path = null) {
    this.folderBrowserModal.style.display = "flex";
    this.currentBrowserPath.textContent = "Đang tải thư mục...";
    this.browserFolderList.innerHTML = `<div style="font-size: 0.8rem; padding: 10px; color: var(--text-tertiary);">Đang tải...</div>`;

    try {
      const url = path ? `/api/fs/browse?path=${encodeURIComponent(path)}` : "/api/fs/browse";
      const res = await fetch(url);
      const data = await res.json();

      this.currentBrowserPathVal = data.current_path;
      this.parentBrowserPathVal = data.parent_path;
      this.currentBrowserPath.textContent = data.current_path;
      this.btnFolderUp.disabled = !data.parent_path;

      this.browserFolderList.innerHTML = "";
      if (data.folders.length === 0) {
        this.browserFolderList.innerHTML = `<div style="font-size: 0.8rem; padding: 10px; color: var(--text-tertiary);">Không có thư mục con nào.</div>`;
        return;
      }

      data.folders.forEach((folder) => {
        const item = document.createElement("div");
        item.className = "folder-entry";
        item.innerHTML = `<span>📁</span> <span>${this.escapeHTML(folder.name)}</span>`;
        item.addEventListener("click", () => {
          this.openFolderBrowser(folder.path);
        });
        this.browserFolderList.appendChild(item);
      });
    } catch (err) {
      this.browserFolderList.innerHTML = `<div style="color: var(--status-danger); padding: 10px;">Lỗi duyệt thư mục: ${err}</div>`;
    }
  }

  async fetchLessons() {
    try {
      const res = await fetch("/api/memory/lessons");
      this.lessons = await res.json();
      if (!this.lessonsGrid) return;
      this.lessonsGrid.innerHTML = "";
      if (this.lessons.length === 0) {
        this.lessonsGrid.innerHTML = `<div style="font-size: 0.8rem; color: var(--text-tertiary); padding: 10px;">Chưa có bài học nào được ghi lại.</div>`;
        return;
      }
      this.lessons.forEach((l) => {
        const card = document.createElement("div");
        card.className = "lesson-card";
        card.innerHTML = `
          <div class="lesson-header">
            <span class="lesson-domain-badge">${l.domain}</span>
            <span style="font-size: 0.7rem; color: var(--text-tertiary);">${l.id} • Đã áp dụng ${l.applied_count || 0} lần</span>
          </div>
          <div class="lesson-trigger">⚠ Tình huống: ${this.escapeHTML(l.trigger_error)}</div>
          <div class="lesson-cause"><strong>Nguyên nhân:</strong> ${this.escapeHTML(l.root_cause)}</div>
          <div class="lesson-learned">✔ <strong>Bài học rút ra:</strong> ${this.escapeHTML(l.lesson_learned)}</div>
          ${l.recommended_pattern ? `<div class="lesson-pattern">Khuyến nghị áp dụng:\n${this.escapeHTML(l.recommended_pattern)}</div>` : ""}
        `;
        this.lessonsGrid.appendChild(card);
      });
    } catch (err) {
      console.error("Fetch lessons error:", err);
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

  /* ========================================================================
     Graphify Code Knowledge Graph Handlers
     ======================================================================== */

  getCurrentProjectPath() {
    return (this.openProjPath && this.openProjPath.value.trim()) || "";
  }

  async fetchGraphSummary() {
    if (this.graphNodesCount && this.graphNodesCount.textContent === "0") {
      this.graphNodesCount.textContent = "⏳...";
      this.graphEdgesCount.textContent = "⏳...";
    }
    try {
      const curPath = this.getCurrentProjectPath();
      const url = curPath ? `/api/graph/summary?path=${encodeURIComponent(curPath)}` : "/api/graph/summary";
      const res = await fetch(url);
      const data = await res.json();
      if (!data.available) {
        if (this.graphQueryResult) {
          this.graphQueryResult.style.display = "block";
          this.graphQueryResult.textContent = "Graphify chưa sẵn sàng hoặc không tìm thấy mã nguồn.";
        }
        return;
      }

      if (this.btnOpenGraphVisualizer) {
        this.btnOpenGraphVisualizer.href = curPath ? `/api/graph/view?path=${encodeURIComponent(curPath)}` : "/api/graph/view";
      }

      if (this.graphNodesCount) this.graphNodesCount.textContent = data.total_nodes.toLocaleString();
      if (this.graphEdgesCount) this.graphEdgesCount.textContent = data.total_edges.toLocaleString();
      if (this.graphGodsCount) this.graphGodsCount.textContent = (data.god_nodes || []).length;
      if (this.graphCyclesCount) {
        const cyclesLen = (data.import_cycles || []).length;
        this.graphCyclesCount.textContent = `${cyclesLen} cycles`;
        this.graphCyclesCount.style.color = cyclesLen > 0 ? "var(--status-danger)" : "var(--status-success)";
      }

      if (this.graphGodNodesList) {
        this.graphGodNodesList.innerHTML = "";
        if (!data.god_nodes || data.god_nodes.length === 0) {
          this.graphGodNodesList.innerHTML = `<span style="font-size: 0.75rem; color: var(--text-tertiary);">Chưa phát hiện God node nào.</span>`;
        } else {
          data.god_nodes.forEach((g) => {
            const badge = document.createElement("span");
            badge.className = "brand-badge";
            badge.style.cursor = "pointer";
            badge.style.fontSize = "0.74rem";
            badge.textContent = `👑 ${g.label || g.id} (${g.degree} liên kết)`;
            badge.addEventListener("click", () => {
              if (this.graphSymbolInput) {
                this.graphSymbolInput.value = g.label || g.id;
                this.handleGraphQuery();
              }
            });
            this.graphGodNodesList.appendChild(badge);
          });
        }
      }
    } catch (err) {
      console.error("Fetch graph summary error:", err);
    }
  }

  async handleGraphQuery() {
    const symbol = this.graphSymbolInput ? this.graphSymbolInput.value.trim() : "";
    if (!symbol) {
      alert("Vui lòng nhập tên class, hàm hoặc module để tra cứu.");
      return;
    }

    if (this.graphQueryResult) {
      this.graphQueryResult.style.display = "block";
      this.graphQueryResult.textContent = `⌛ Đang tra cứu quan hệ cho '${symbol}'...`;
    }

    try {
      const curPath = this.getCurrentProjectPath();
      const url = `/api/graph/query?symbol=${encodeURIComponent(symbol)}${curPath ? `&path=${encodeURIComponent(curPath)}` : ""}`;
      const res = await fetch(url);
      const data = await res.json();
      if (!data.found) {
        this.graphQueryResult.textContent = `❌ ${data.message || "Không tìm thấy symbol trong đồ thị."}`;
        return;
      }

      let out = `📌 Symbol: ${data.label} (ID: ${data.id})\n`;
      out += `📁 Tệp tin: ${data.file || "N/A"} ${data.location ? `[${data.location}]` : ""}\n`;
      out += `🔗 Bậc liên kết (Degree): ${data.degree} (${data.connections_count} kết nối)\n\n`;
      out += `DANH SÁCH LIÊN KẾT TRỰC TIẾP:\n`;
      (data.connections || []).forEach((c, idx) => {
        out += `${idx + 1}. [${c.relation}] ➔ ${c.label} (${c.file || "external"})\n`;
      });

      this.graphQueryResult.textContent = out;
    } catch (err) {
      this.graphQueryResult.textContent = `Lỗi tra cứu đồ thị: ${err}`;
    }
  }

  async handleGraphImpact() {
    const symbol = this.graphSymbolInput ? this.graphSymbolInput.value.trim() : "";
    if (!symbol) {
      alert("Vui lòng nhập tên class, hàm hoặc module để phân tích tác động.");
      return;
    }

    if (this.graphQueryResult) {
      this.graphQueryResult.style.display = "block";
      this.graphQueryResult.textContent = `⚡ Đang tính toán phạm vi ảnh hưởng (Blast Radius) khi sửa '${symbol}'...`;
    }

    try {
      const curPath = this.getCurrentProjectPath();
      const url = `/api/graph/impact?symbol=${encodeURIComponent(symbol)}&depth=2${curPath ? `&path=${encodeURIComponent(curPath)}` : ""}`;
      const res = await fetch(url);
      const data = await res.json();
      if (!data.found) {
        this.graphQueryResult.textContent = `❌ ${data.message || "Không tìm thấy symbol."}`;
        return;
      }

      let out = `⚡ KẾT QUẢ PHÂN TÍCH TÁC ĐỘNG (BLAST RADIUS):\n`;
      out += `🎯 Mục tiêu: ${data.target_symbol} (Node: ${data.target_node})\n`;
      out += `⚠ Mức độ rủi ro (Risk Level): [${data.risk_level}]\n`;
      out += `📊 Tổng số thành phần bị ảnh hưởng: ${data.total_affected_components}\n\n`;

      (data.depth_layers || []).forEach((layer, lIdx) => {
        out += `--- Cấp độ ảnh hưởng ${lIdx + 1} (${layer.length} thành phần) ---\n`;
        layer.forEach((item, idx) => {
          out += `  • ${item.label} (${item.file}) [qua ${item.depends_via}: ${item.relation}]\n`;
        });
      });

      this.graphQueryResult.textContent = out;
    } catch (err) {
      this.graphQueryResult.textContent = `Lỗi phân tích tác động: ${err}`;
    }
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
