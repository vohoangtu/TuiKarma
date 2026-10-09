"""Unit tests for Sandboxed Filesystem Snapshot & Saga Rollback."""

import pytest
from pathlib import Path
from tuikarma.tools.snapshot import SandboxSnapshotManager
from tuikarma.workflow.engine import WorkflowEngine
from tuikarma.workflow.node import BaseWorkflowNode
from tuikarma.workflow.state import WorkflowState, NodeResult
from tuikarma.core.event_bus import EventBus


def test_snapshot_capture_and_restore(tmp_path: Path):
    manager = SandboxSnapshotManager(tmp_path)

    # Initial state: create file a.txt
    (tmp_path / "a.txt").write_text("Hello A", encoding="utf-8")
    manager.create_checkpoint("cp1")

    # Change 1: modify a.txt, create b.txt, create subfolder/c.txt
    (tmp_path / "a.txt").write_text("Hello Modified A", encoding="utf-8")
    (tmp_path / "b.txt").write_text("Hello B", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.txt").write_text("Hello C", encoding="utf-8")

    diff = manager.get_diff("cp1")
    assert "b.txt" in diff["added"]
    assert "sub/c.txt" in diff["added"]
    assert "a.txt" in diff["modified"]

    # Restore checkpoint 1
    actions = manager.restore_checkpoint("cp1")
    assert any("removed" in a for a in actions)

    # Assert exact restoration
    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "Hello A"
    assert not (tmp_path / "b.txt").exists()
    assert not (sub / "c.txt").exists()


@pytest.mark.asyncio
async def test_workflow_engine_disk_snapshot_rollback(tmp_path: Path):
    bus = EventBus()
    engine = WorkflowEngine("Test Disk Rollback", bus=bus, workspace_dir=tmp_path)

    class FileWriteNode(BaseWorkflowNode):
        def __init__(self, node_id: str, filename: str, content: str, should_fail: bool = False):
            super().__init__(node_id=node_id, name=node_id, max_retries=1, retry_delay_seconds=0.01)
            self.filename = filename
            self.content = content
            self.should_fail = should_fail

        async def execute(self, state: WorkflowState) -> NodeResult:
            target = tmp_path / self.filename
            target.write_text(self.content, encoding="utf-8")
            if self.should_fail:
                return NodeResult(node_id=self.node_id, success=False, error_message="Simulated error")
            return NodeResult(node_id=self.node_id, success=True, output=f"Wrote {self.filename}")

    # Node 1 writes file1.py
    node1 = FileWriteNode("step1", "file1.py", "print('Step 1')")
    # Node 2 writes file2.py
    node2 = FileWriteNode("step2", "file2.py", "print('Step 2')")
    # Node 3 writes bad.py and fails
    node3 = FileWriteNode("step3", "bad.py", "syntax error", should_fail=True)

    engine.add_node(node1, is_start=True)
    engine.add_node(node2)
    engine.add_node(node3, is_end=True)

    engine.add_edge("step1", "step2")
    engine.add_edge("step2", "step3")

    state = await engine.execute()

    assert state.is_failed is True
    assert "step2" in state.rolled_back_nodes
    assert "step1" in state.rolled_back_nodes

    # Verify physical files on disk after reverse saga rollback:
    # Everything rolled back to before step1 (which was an empty workspace)
    assert not (tmp_path / "file1.py").exists()
    assert not (tmp_path / "file2.py").exists()
    assert not (tmp_path / "bad.py").exists()
