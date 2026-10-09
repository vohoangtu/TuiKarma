"""Standard workflow builders for common multi-agent patterns (Self-healing Code-Test-Review)."""

from __future__ import annotations
from typing import TYPE_CHECKING
from tuikarma.workflow.engine import WorkflowEngine
from tuikarma.workflow.node import AgentWorkflowNode, DecisionWorkflowNode
from tuikarma.workflow.state import WorkflowState

if TYPE_CHECKING:
    from tuikarma.core.topology import SwarmTopology


def build_self_healing_coding_workflow(swarm: SwarmTopology) -> WorkflowEngine:
    """Builds a cyclic, self-healing Multi-Agent Coding Workflow (Plan -> Code -> Test -> [Fix] -> Review -> Conclude)."""
    engine = WorkflowEngine(
        name="Self-Healing Code-Test-Review Workflow",
        bus=swarm.bus,
        max_steps=12,
        workspace_dir=swarm.workspace_dir
    )

    supervisor = swarm.agents["Supervisor"]
    coder = swarm.agents["Coder"]
    tester = swarm.agents["Tester"]
    critic = swarm.agents["Critic"]

    # 1. Plan Node
    engine.add_node(
        AgentWorkflowNode(
            node_id="plan",
            name="Lập kế hoạch kiến trúc (Supervisor)",
            agent=supervisor,
            prompt_template="Mục tiêu nhiệm vụ: {task_description}. Hãy phân tích yêu cầu, thiết kế kiến trúc và phân công cho Coder, Tester, Critic."
        ),
        is_start=True
    )

    # 2. Code Node
    engine.add_node(
        AgentWorkflowNode(
            node_id="code",
            name="Triển khai mã nguồn (Coder)",
            agent=coder,
            prompt_template="Kế hoạch của Supervisor: {plan}. Hãy viết mã nguồn đầy đủ, chuẩn type hints và dùng công cụ write_file lưu vào sandbox."
        )
    )

    # 3. Test Node
    engine.add_node(
        AgentWorkflowNode(
            node_id="test",
            name="Kiểm thử tự động (Tester)",
            agent=tester,
            prompt_template="Mã nguồn vừa được Coder tạo ra: {code}. Hãy thiết kế unit tests, dùng write_file và run_command để chạy pytest kiểm tra lỗi."
        )
    )

    # 4. Decision Node: Check if test passed or if fixing is needed
    def evaluate_test_results(state: WorkflowState) -> str:
        test_output = str(state.get_output("test", ""))
        fix_iterations = state.iterations.get("fix_code", 0)

        # If test output mentions failure/error and we haven't exceeded retry limit
        has_failure = any(kw in test_output.lower() for kw in ["failed", "error", "traceback", "assertionerror"])
        if has_failure and fix_iterations < 2:
            return "fix_code"
        return "review"

    engine.add_node(
        DecisionWorkflowNode(
            node_id="evaluate_test",
            name="Đánh giá kết quả test (Decision Gateway)",
            decision_fn=evaluate_test_results
        )
    )

    # 5. Fix Code Node (Self-Healing Loop)
    engine.add_node(
        AgentWorkflowNode(
            node_id="fix_code",
            name="Sửa lỗi theo feedback test (Coder Patch)",
            agent=coder,
            prompt_template="Phát hiện lỗi kiểm thử: {test}. Hãy phân tích nguyên nhân và dùng write_file để cập nhật bản vá sửa lỗi."
        )
    )

    # 6. Review Node
    engine.add_node(
        AgentWorkflowNode(
            node_id="review",
            name="Đánh giá chất lượng & bảo mật (Critic)",
            agent=critic,
            prompt_template="Mã nguồn đã qua test: {code}. Đánh giá kiến trúc, PEP-8, rủi ro bảo mật và đưa ra kết luận chấp thuận (APPROVED) hoặc khuyến nghị."
        )
    )

    # 7. Synthesize Node (End)
    engine.add_node(
        AgentWorkflowNode(
            node_id="synthesize",
            name="Tổng hợp & Nghiệm thu (Supervisor)",
            agent=supervisor,
            prompt_template="Kết quả review: {review}. Hãy tổng kết toàn bộ quá trình, xác nhận các file đã hoàn thành và nghiệm thu nhiệm vụ."
        ),
        is_end=True
    )

    # Setup Edges
    engine.add_edge("plan", "code", name="Kế hoạch hoàn tất -> Viết code")
    engine.add_edge("code", "test", name="Code hoàn tất -> Kiểm thử")
    engine.add_edge("test", "evaluate_test", name="Đánh giá kết quả kiểm thử")
    # evaluate_test routes via DecisionWorkflowNode (to 'fix_code' or 'review')
    engine.add_edge("fix_code", "test", name="Đã vá lỗi -> Chạy lại kiểm thử (Feedback Loop)")
    engine.add_edge("review", "synthesize", name="Review hoàn tất -> Nghiệm thu cuối")

    return engine
