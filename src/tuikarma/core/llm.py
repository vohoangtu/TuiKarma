"""Universal LLM Provider Gateway for TUIKarma (Local Gateway, Antigravity & Scenario)."""

from __future__ import annotations
import os
import re
import json
import asyncio
import urllib.request
import urllib.error
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field


class ToolCallData(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    content: str
    thought: Optional[str] = None
    tool_calls: List[ToolCallData] = Field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0


class BaseLLMProvider:
    """Base interface for LLM backends."""

    async def generate(
        self,
        model_name: str,
        system_prompt: str,
        messages: List[Dict[str, str]],
        tools_schema: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        raise NotImplementedError


class LocalGatewayLLMProvider(BaseLLMProvider):
    """Connects to the local OpenAI-compatible gateway (e.g. OmniRoute/Antigravity at http://localhost:20128/v1)."""

    def __init__(
        self,
        base_url: str = "http://localhost:20128/v1",
        api_key: str = "sk-antigravity",
        timeout: float = 40.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    async def generate(
        self,
        model_name: str,
        system_prompt: str,
        messages: List[Dict[str, str]],
        tools_schema: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        full_messages = [{"role": "system", "content": system_prompt}]
        for m in messages:
            # Map memory roles
            role = m.get("role", "user")
            if role == "thought":
                continue
            full_messages.append({"role": role, "content": m.get("content", "")})

        payload: Dict[str, Any] = {
            "model": model_name,
            "messages": full_messages,
            "temperature": 0.2,
        }

        # Format OpenAI tool specifications if tools provided
        if tools_schema:
            tools_payload = []
            for t in tools_schema:
                tools_payload.append({
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "filepath": {"type": "string", "description": "Tên hoặc đường dẫn file"},
                                "content": {"type": "string", "description": "Nội dung file"},
                                "code": {"type": "string", "description": "Mã Python cần thực thi"},
                                "command": {"type": "string", "description": "Lệnh CLI cần thực thi"},
                            }
                        }
                    }
                })
            payload["tools"] = tools_payload
            payload["tool_choice"] = "auto"

        def _do_request() -> Dict[str, Any]:
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                }
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))

        try:
            res_data = await asyncio.to_thread(_do_request)
            choice = res_data["choices"][0]
            message = choice.get("message", {})
            raw_content = message.get("content") or ""

            # Check reasoning/thought
            thought = message.get("reasoning_content") or message.get("thought")
            content = raw_content

            if not thought and "<thought>" in raw_content:
                match = re.search(r"<thought>(.*?)</thought>", raw_content, re.DOTALL)
                if match:
                    thought = match.group(1).strip()
                    content = re.sub(r"<thought>.*?</thought>", "", raw_content, flags=re.DOTALL).strip()

            # Parse tool calls
            parsed_tools: List[ToolCallData] = []
            raw_tool_calls = message.get("tool_calls") or []
            for tc in raw_tool_calls:
                fn = tc.get("function", {})
                tool_name = fn.get("name", "")
                raw_args = fn.get("arguments", "{}")
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except Exception:
                    args = {}
                parsed_tools.append(ToolCallData(tool_name=tool_name, arguments=args))

            usage = res_data.get("usage", {})
            tokens_in = usage.get("prompt_tokens", 0)
            tokens_out = usage.get("completion_tokens", 0)

            return LLMResponse(
                content=content or "Đã thực hiện xong.",
                thought=thought,
                tool_calls=parsed_tools,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=0.0  # Local gateway = 0 direct cost
            )

        except Exception as e:
            # Fallback message on network/model error
            return LLMResponse(
                content=f"[Local Gateway Error]: {e}",
                thought="Lỗi kết nối tới local gateway, hãy kiểm tra tiến trình OmniRoute/Antigravity.",
                tokens_in=0,
                tokens_out=0,
                cost_usd=0.0
            )


class ScenarioLLMProvider(BaseLLMProvider):
    """Deterministic scenario-driven LLM provider for benchmark testing & offline demo."""

    def __init__(self) -> None:
        self.step_counter: Dict[str, int] = {}

    async def generate(
        self,
        model_name: str,
        system_prompt: str,
        messages: List[Dict[str, str]],
        tools_schema: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        agent_role = "Worker"
        if "Supervisor" in system_prompt or "orchestrate" in system_prompt.lower():
            agent_role = "Supervisor"
        elif "Coder" in system_prompt or "code" in system_prompt.lower():
            agent_role = "Coder"
        elif "Tester" in system_prompt or "test" in system_prompt.lower():
            agent_role = "Tester"
        elif "Critic" in system_prompt or "review" in system_prompt.lower():
            agent_role = "Critic"

        current_step = self.step_counter.get(agent_role, 1)
        self.step_counter[agent_role] = current_step + 1

        await asyncio.sleep(0.3)

        if agent_role == "Supervisor":
            return LLMResponse(
                content="Kế hoạch thực hiện: Coder viết mã nguồn core, Tester tạo test suite, Critic đánh giá bảo mật và hiệu năng.",
                thought="Phân rã bài toán thành các sub-tasks độc lập và giao việc theo năng lực chuyên môn.",
                tokens_in=850,
                tokens_out=220,
                cost_usd=0.012
            )
        elif agent_role == "Coder":
            code_sample = (
                "import time\nimport asyncio\n\n"
                "class TokenBucketRateLimiter:\n"
                "    def __init__(self, capacity: int, refill_rate: float) -> None:\n"
                "        self.capacity = capacity\n"
                "        self.tokens = float(capacity)\n"
                "        self.refill_rate = refill_rate\n"
                "        self.last_update = time.monotonic()\n"
                "        self._lock = asyncio.Lock()\n\n"
                "    async def acquire(self, tokens: int = 1) -> bool:\n"
                "        async with self._lock:\n"
                "            now = time.monotonic()\n"
                "            elapsed = now - self.last_update\n"
                "            self.last_update = now\n"
                "            self.tokens = min(float(self.capacity), self.tokens + elapsed * self.refill_rate)\n"
                "            if self.tokens >= tokens:\n"
                "                self.tokens -= tokens\n"
                "                return True\n"
                "            return False\n"
            )
            return LLMResponse(
                content="Đã triển khai xong thuật toán Token Bucket Rate Limiter với thread-safe async lock. Đang ghi file.",
                thought="Sử dụng asyncio.Lock để đảm bảo an toàn bất đồng bộ khi nhiều coroutine cùng gọi acquire().",
                tool_calls=[
                    ToolCallData(
                        tool_name="write_file",
                        arguments={"filepath": "rate_limiter.py", "content": code_sample}
                    )
                ],
                tokens_in=1420,
                tokens_out=480,
                cost_usd=0.025
            )
        elif agent_role == "Tester":
            test_sample = (
                "import pytest\nimport asyncio\nfrom rate_limiter import TokenBucketRateLimiter\n\n"
                "@pytest.mark.asyncio\n"
                "async def test_acquire_burst():\n"
                "    limiter = TokenBucketRateLimiter(capacity=2, refill_rate=1.0)\n"
                "    assert await limiter.acquire(1) is True\n"
                "    assert await limiter.acquire(1) is True\n"
                "    assert await limiter.acquire(1) is False\n"
            )
            return LLMResponse(
                content="Đã tạo test case kiểm thử burst capacity và rate refilling.",
                thought="Kiểm thử tình huống vượt quá capacity ban đầu để xác minh việc từ chối request.",
                tool_calls=[
                    ToolCallData(
                        tool_name="write_file",
                        arguments={"filepath": "tests/test_limiter.py", "content": test_sample}
                    ),
                    ToolCallData(
                        tool_name="run_command",
                        arguments={"command": "python -m pytest tests/test_limiter.py -v"}
                    )
                ],
                tokens_in=1100,
                tokens_out=360,
                cost_usd=0.018
            )
        elif agent_role == "Critic":
            return LLMResponse(
                content="Đánh giá chất lượng: Kiến trúc đạt chuẩn PEP-8, async lock xử lý đúng race condition, test coverage đầy đủ. Chấp thuận kết quả!",
                thought="Soát lỗi concurrency, memory leak và edge cases khi `elapsed` rất nhỏ.",
                tokens_in=1300,
                tokens_out=290,
                cost_usd=0.015
            )

        return LLMResponse(
            content=f"Đã xử lý xong tác vụ từ {agent_role}.",
            tokens_in=500,
            tokens_out=100,
            cost_usd=0.005
        )


def is_local_gateway_available(url: str = "http://localhost:20128/api/health") -> bool:
    """Quick probe to check if the local AI gateway is active."""
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=0.8) as resp:
            return resp.status == 200
    except Exception:
        return False


def get_default_llm_provider(force_backend: Optional[str] = None) -> BaseLLMProvider:
    """Returns the appropriate LLM provider: Local Gateway if available, or Scenario fallback."""
    backend = force_backend or os.environ.get("TUIKARMA_BACKEND", "auto").lower()

    if backend == "scenario":
        return ScenarioLLMProvider()
    elif backend == "local":
        return LocalGatewayLLMProvider()

    # Auto-detection
    if is_local_gateway_available():
        return LocalGatewayLLMProvider()

    return ScenarioLLMProvider()
