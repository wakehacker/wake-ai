from __future__ import annotations

import asyncio
import hashlib
import json
import os
import platform
import random
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, NamedTuple, Literal, Any, cast

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import TextContent
from openai import APIError, AsyncOpenAI, omit
from openai.types.responses import EasyInputMessageParam, FunctionToolParam, ResponseIncompleteEvent, ResponseAudioDeltaEvent, ResponseCompletedEvent, ResponseCreatedEvent, ResponseFunctionCallArgumentsDeltaEvent, ResponseFunctionCallArgumentsDoneEvent, ResponseFunctionShellCallOutputContentParam, ResponseFunctionShellToolCall, ResponseFunctionToolCall, ResponseInProgressEvent, ResponseOutputItemAddedEvent, ResponseOutputItemDoneEvent, ResponseOutputMessage, ResponseOutputRefusal, ResponseOutputText, ResponseReasoningItem, ResponseTextConfigParam, ResponseTextDeltaEvent, ResponseTextDoneEvent, ToolParam
from openai.types.responses.function_shell_tool import FunctionShellTool
from openai.types.responses.response_function_shell_call_output_content_param import OutcomeExit, OutcomeTimeout
from openai.types.responses.response_input_item_param import ResponseInputItemParam
from openai.types.responses.response_input_param import FunctionCallOutput, ShellCallOutput
from openai.types.shared_params import ResponseFormatText
from openai.types.shared_params.reasoning import Reasoning

from .codex_pricing import GPT_PRICING
from .landlock import run_under_landlock
from .seatbelt import run_under_seatbelt
from .session_abc import SessionABC, FunctionTool
from .verbose_formatter import VerboseFormatter
from ..utils.logging import get_logger

logger = get_logger(__name__)


class OpenAIResponse(NamedTuple):
    cost: float
    status: Literal["running", "terminating_on_max_cost", "succeeded", "terminated", "errored"]


def _compute_backoff_time(retry: int) -> float:
    # base time is 20 seconds, exponential growth; 10% jitter
    # retry starts at 0
    exp = 2.0 ** retry
    base = 20 * exp
    return base * random.uniform(0.9, 1.1)


LEGACY_SHELL_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "commands": {
            "type": "array",
            "description": "A list of shell commands to execute. Execution in order is NOT guaranteed.",
            "items": {
                "type": "string",
            },
        },
        "timeout_ms": {
            "type": "number",
            "description": "The timeout in milliseconds for each command.",
        },
        "max_output_length": {
            "type": "integer",
            "description": "The maximum output length in characters for each command.",
        },
    },
    "required": ["commands", "timeout_ms"],
}

MAX_COMPACTIONS = 5

# Models that support OpenAI's native shell tool (FunctionShellTool).
# All others fall back to the legacy "shell" function workaround.
_NATIVE_SHELL_MODEL_PREFIXES = ("gpt-5.1", "gpt-5.2", "gpt-5.4")

# OpenAI limits function names to 64 characters ([A-Za-z0-9_-] only).
_OPENAI_MAX_TOOL_NAME_LEN = 64
_ALIAS_HASH_LEN = 8  # hex chars appended when the slug must be shortened


def _slugify(s: str) -> str:
    """Replace characters outside [A-Za-z0-9_-] with underscore."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", s)


def _mcp_tool_alias(server_name: str, tool_name: str) -> str:
    """Return a stable OpenAI-safe function name for an MCP tool.

    Format: ``<server>__<tool>`` (both parts slugified). If the result exceeds
    64 characters, the slug is truncated and an 8-hex-char SHA-256 suffix of
    the original names is appended so the alias stays both within the limit
    and stable across restarts.
    """
    slug = f"{_slugify(server_name)}__{_slugify(tool_name)}"
    if len(slug) <= _OPENAI_MAX_TOOL_NAME_LEN:
        return slug
    h = hashlib.sha256(f"{server_name}\x00{tool_name}".encode()).hexdigest()[:_ALIAS_HASH_LEN]
    return f"{slug[:_OPENAI_MAX_TOOL_NAME_LEN - _ALIAS_HASH_LEN - 1]}_{h}"


def _resolve_mcp_alias(
    server_name: str,
    tool_name: str,
    reserved: set[str],
    registered: dict[str, Any],
) -> str | None:
    """Return a unique OpenAI-safe alias for an MCP tool, or ``None`` if impossible.

    Tries the primary slug first; if it collides, a hash-disambiguated form is
    used. Returns ``None`` (with error log) only if both forms are already taken.
    """
    alias = _mcp_tool_alias(server_name, tool_name)
    if alias not in reserved and alias not in registered:
        return alias

    h = hashlib.sha256(f"{server_name}\x00{tool_name}".encode()).hexdigest()[:_ALIAS_HASH_LEN]
    disambiguated = f"{alias[:_OPENAI_MAX_TOOL_NAME_LEN - _ALIAS_HASH_LEN - 1]}_{h}"
    logger.warning(
        "MCP tool '%s' from '%s' has conflicting alias '%s'; "
        "registering as '%s' instead.",
        tool_name, server_name, alias, disambiguated,
    )
    if disambiguated in reserved or disambiguated in registered:
        logger.error(
            "Cannot register MCP tool '%s' from '%s': "
            "disambiguated alias '%s' also taken. Skipping.",
            tool_name, server_name, disambiguated,
        )
        return None
    return disambiguated


class OpenAITokenUsage:
    input_tokens_total: int
    input_tokens_cached: int
    output_tokens: int
    cost: float

    def __init__(self, input_tokens_total: int = 0, input_tokens_cached: int = 0, output_tokens: int = 0) -> None:
        self.input_tokens_total = input_tokens_total
        self.input_tokens_cached = input_tokens_cached
        self.output_tokens = output_tokens
        self.cost = 0.0

    def update(self, model: str, tier: Literal["flex", "standard", "priority"], input_tokens_total: int, input_tokens_cached: int, output_tokens: int) -> None:
        self.input_tokens_total += input_tokens_total
        self.input_tokens_cached += input_tokens_cached
        self.output_tokens += output_tokens

        input_cost = (input_tokens_total - input_tokens_cached) * GPT_PRICING[model][tier].input_mtoken_cost / 1e6
        cached_input_cost = input_tokens_cached * GPT_PRICING[model][tier].cached_input_mtoken_cost / 1e6
        output_cost = output_tokens * GPT_PRICING[model][tier].output_mtoken_cost / 1e6

        if model in {"gpt-5.4", "gpt-5.4-pro"} and input_tokens_total >= 272_000:
            input_cost *= 2
            cached_input_cost *= 2
            output_cost *= 1.5

        self.cost += input_cost + cached_input_cost + output_cost


class OpenAITotalTokenUsage:
    usage: dict[str, dict[Literal["flex", "standard", "priority"], OpenAITokenUsage]]

    def __init__(self) -> None:
        self.usage = {}

    @property
    def total_tokens(self) -> OpenAITokenUsage:
        return OpenAITokenUsage(
            input_tokens_total=sum(usage.input_tokens_total for tiered_usage in self.usage.values() for usage in tiered_usage.values()),
            input_tokens_cached=sum(usage.input_tokens_cached for tiered_usage in self.usage.values() for usage in tiered_usage.values()),
            output_tokens=sum(usage.output_tokens for tiered_usage in self.usage.values() for usage in tiered_usage.values()),
        )

    @property
    def total_cost(self) -> float:
        total_cost = 0.0
        for model, tiered_usage in self.usage.items():
            for tier, usage in tiered_usage.items():
                total_cost += usage.cost
        return total_cost

    def update(
        self,
        input_tokens_total: int,
        input_tokens_cached: int,
        output_tokens: int,
        model: str,
        tier: Literal["flex", "standard", "priority"],
    ) -> None:
        if model not in self.usage:
            self.usage[model] = {
                "flex": OpenAITokenUsage(),
                "standard": OpenAITokenUsage(),
                "priority": OpenAITokenUsage(),
            }
        self.usage[model][tier].update(model, tier, input_tokens_total, input_tokens_cached, output_tokens)


@dataclass
class SSEServerParameters:
    url: str
    headers: dict[str, str] | None = None
    timeout: float = 5
    sse_read_timeout: float = 60 * 5


@dataclass
class StreamableHTTPServerParameters:
    url: str
    headers: dict[str, str] | None = None
    timeout: float = 5
    sse_read_timeout: float = 60 * 5
    terminate_on_close: bool = False


class ResponseIncompleteError(Exception):
    reason: str | None

    def __init__(self, reason: str | None) -> None:
        self.reason = reason

    def __str__(self) -> str:
        return f"Response incomplete: {self.reason}"


class OpenAISession(SessionABC):
    execution_dir: Path
    fork_session: OpenAISession | None
    instructions: str | None
    service_tier: Literal["auto", "default", "flex", "scale", "priority"] | None
    reasoning_effort: Literal["none", "low", "medium", "high", "xhigh"] | None
    reasoning_summary: Literal["auto", "concise", "detailed"] | None
    output_verbosity: Literal["low", "medium", "high"] | None
    max_retries: int
    request_timeout: float | None
    tools: dict[str, FunctionTool]
    shell: bool
    mcps: dict[str, ClientSession | StdioServerParameters | SSEServerParameters | StreamableHTTPServerParameters]
    network_access: bool
    writable_roots: list[Path | str]

    client: AsyncOpenAI
    _session_id: str | None
    conversation: list[ResponseInputItemParam]
    total_token_usage: OpenAITotalTokenUsage

    def __init__(
        self,
        execution_dir: Path,
        *,
        fork_session: OpenAISession | None = None,
        instructions: str | None = None,
        service_tier: Literal["auto", "default", "flex", "scale", "priority"] | None = None,
        reasoning_effort: Literal["none", "low", "medium", "high", "xhigh"] | None = None,
        reasoning_summary: Literal["auto", "concise", "detailed"] | None = None,
        output_verbosity: Literal["low", "medium", "high"] | None = None,
        max_retries: int = 5,
        request_timeout: float | None = 600,  # 10 minutes
        tools: list[FunctionTool] | None = None,
        shell: bool = True,
        mcps: dict[str, ClientSession | StdioServerParameters | SSEServerParameters | StreamableHTTPServerParameters] | None = None,
        network_access: bool = False,
        writable_roots: list[Path | str] | None = None,
    ):
        self.execution_dir = execution_dir
        self.fork_session = fork_session
        self.instructions = instructions
        self.service_tier = service_tier
        self.reasoning_effort = reasoning_effort
        self.reasoning_summary = reasoning_summary
        self.output_verbosity = output_verbosity
        self.max_retries = max_retries
        self.request_timeout = request_timeout
        self.shell = shell
        self.mcps = mcps or {}
        self.network_access = network_access
        self.writable_roots = writable_roots or []

        self.tools = {}
        if tools is not None:
            for tool in tools:
                self.tools[tool.name] = tool

        self.client = AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
        )
        if fork_session is not None:
            if not fork_session.conversation:
                raise ValueError("Forking from OpenAISession with empty conversation")
            self.conversation = fork_session.conversation.copy()
        else:
            self.conversation = []
        self._session_id = None
        self.total_token_usage = OpenAITotalTokenUsage()

    @property
    def session_id(self) -> str | None:
        return self._session_id

    async def _call_tool(self, tool_call: ResponseFunctionToolCall) -> Any:
        tool = self.tools[tool_call.name]

        if tool_call.arguments:
            input = json.loads(tool_call.arguments)
        else:
            input = {}

        return await tool.handler(**input)

    async def _call_shell(self, commands: list[str], timeout_ms: int | None, max_output_length: int | None) -> list[ResponseFunctionShellCallOutputContentParam]:
        if platform.system() not in {"Darwin", "Linux"}:
            raise NotImplementedError("Shell tools are only supported on macOS and Linux")

        timeout = timeout_ms / 1000.0 if timeout_ms is not None else None
        max_length = max_output_length if max_output_length is not None else 1000000

        output: list[ResponseFunctionShellCallOutputContentParam] = []

        for command in commands:
            try:
                writable_roots = [Path(root) for root in self.writable_roots]
                if platform.system() == "Darwin":
                    stdout, stderr, returncode = await run_under_seatbelt(command, self.network_access, writable_roots, timeout, self.execution_dir)
                else:
                    stdout, stderr, returncode = await run_under_landlock(command, self.network_access, writable_roots, timeout, self.execution_dir)

                output.append(ResponseFunctionShellCallOutputContentParam(
                    outcome=OutcomeExit(
                        exit_code=returncode,
                        type="exit",
                    ),
                    stderr=stderr[:max_length],
                    stdout=stdout[:max_length],
                ))
            except asyncio.TimeoutError:
                output.append(ResponseFunctionShellCallOutputContentParam(
                    outcome=OutcomeTimeout(
                        type="timeout",
                    ),
                    stderr="",
                    stdout="",
                ))

        return output

    async def _call_legacy_shell(self, arguments: str) -> list[ResponseFunctionShellCallOutputContentParam]:
        args = json.loads(arguments)
        if "commands" not in args:
            raise ValueError("commands not found in arguments")
        if "timeout_ms" not in args:
            raise ValueError("timeout_ms not found in arguments")

        return await self._call_shell(args["commands"], args["timeout_ms"], args.get("max_output_length", None))

    async def _call_mcp_tool(self, client: ClientSession, tool_name: str, arguments: str) -> Any:
        args = json.loads(arguments) if arguments else {}

        # TODO: read timeout seconds
        result = await client.call_tool(tool_name, args)

        if result.structuredContent is not None:
            return {"isError": result.isError, "structuredContent": result.structuredContent}
        else:
            return {"isError": result.isError, "content": "\n".join(c.text for c in result.content if isinstance(c, TextContent))}

    async def _stream_messages(self, prompt: str, model: str, mcp_clients: dict[str, ClientSession], formatter: VerboseFormatter) -> AsyncIterator[float]:
        tools: list[ToolParam] = [
            FunctionToolParam(
                name=tool.name,
                parameters=tool.input_schema,
                description=tool.description,
                type="function",
                strict=False,
            ) for tool in self.tools.values()
        ]

        _use_native_shell = model.startswith(_NATIVE_SHELL_MODEL_PREFIXES)

        _reserved_aliases: set[str] = set(self.tools.keys())
        mcp_tools: dict[str, tuple[ClientSession, str]] = {}  # alias -> (client, original_tool_name)

        for server_name, client in mcp_clients.items():
            cursor = None
            while True:
                response = await client.list_tools(cursor=cursor)
                for tool in response.tools:
                    alias = _resolve_mcp_alias(
                        server_name, tool.name, _reserved_aliases, mcp_tools
                    )
                    if alias is None:
                        continue

                    mcp_tools[alias] = (client, tool.name)
                    tools.append(FunctionToolParam(
                        name=alias,
                        parameters=tool.inputSchema,
                        description=tool.description,
                        type="function",
                        strict=False,
                    ))
                if response.nextCursor is None:
                    break
                cursor = response.nextCursor

        if self.shell:
            # TODO: workaround for bug on OpenAI's server side
            if True:
            # if not _use_native_shell:
                tools.append(FunctionToolParam(
                    name="shell",
                    parameters=LEGACY_SHELL_INPUT_SCHEMA,
                    description="Execute multiple shell commands in parallel",
                    type="function",
                    strict=False,
                ))
            else:
                tools.append(FunctionShellTool(type="shell"))

        retry = 0
        service_tier = self.service_tier or "standard"
        last_flex_successful = True
        compact_reason: str | None = None
        compact_count = 0

        self.conversation.append(EasyInputMessageParam(content=prompt, role="user", type="message"))

        while True:
            try:
                if compact_reason is not None:
                    compact_count += 1
                    if compact_count > MAX_COMPACTIONS:
                        raise RuntimeError("max_compactions_reached")

                    formatter.print_system_message(f"Compacting conversation ({compact_count}/{MAX_COMPACTIONS})")

                    compacted = await self.client.responses.compact(
                        model=model,
                        input=self.conversation,
                        instructions=self.instructions or omit,
                        timeout=self.request_timeout,
                    )
                    self.total_token_usage.update(
                        input_tokens_total=compacted.usage.input_tokens,
                        input_tokens_cached=compacted.usage.input_tokens_details.cached_tokens,
                        output_tokens=compacted.usage.output_tokens,
                        model=model,
                        tier="standard",
                    )
                    self.conversation = cast(
                        list[ResponseInputItemParam],
                        [item.model_dump(mode="json", exclude_none=True) for item in compacted.output],
                    )
                    if compact_reason == "max_output_tokens":
                        self.conversation.append(EasyInputMessageParam(content="continue", role="user", type="message"))
                    compact_reason = None

                stream = await self.client.responses.create(
                    input=self.conversation,
                    model=model,
                    instructions=self.instructions or omit,
                    service_tier="default" if service_tier == "standard" else service_tier,
                    tools=tools or omit,
                    stream=True,
                    store=False,
                    reasoning=Reasoning(
                        effort=self.reasoning_effort,
                        summary=self.reasoning_summary,
                    ),
                    text=ResponseTextConfigParam(
                        format=ResponseFormatText(
                            type="text",
                        ),
                        verbosity=self.output_verbosity,
                    ),
                    timeout=self.request_timeout,
                    include=["reasoning.encrypted_content"],
                )

                last_event = None
                tool_calls: dict[str, asyncio.Task[Any]] = {}
                shell_calls: dict[str, tuple[asyncio.Task[list[ResponseFunctionShellCallOutputContentParam]], ResponseFunctionShellToolCall]] = {}

                async for event in stream:
                    last_event = event
                    if isinstance(event, ResponseCreatedEvent):
                        pass
                    elif isinstance(event, ResponseInProgressEvent):
                        pass
                    elif isinstance(event, ResponseTextDeltaEvent):
                        pass
                    elif isinstance(event, ResponseTextDoneEvent):
                        pass  # already printed in ResponseOutputItemDoneEvent - ResponseOutputMessage
                    elif isinstance(event, ResponseOutputItemAddedEvent):
                        pass
                    elif isinstance(event, ResponseOutputItemDoneEvent):
                        if isinstance(event.item, ResponseOutputMessage):
                            for content in event.item.content:
                                if isinstance(content, ResponseOutputText):
                                    formatter.print_agent_message(content.text)
                                elif isinstance(content, ResponseOutputRefusal):
                                    formatter.print_agent_message(content.refusal)
                        elif isinstance(event.item, ResponseFunctionToolCall):
                            formatter.print_tool_use(event.item.name, event.item.arguments)

                            # TODO: workaround for bug on OpenAI's server side
                            if event.item.name == "shell" and True:
                            # if event.item.name == "shell" and not _use_native_shell:
                                tool_calls[event.item.call_id] = asyncio.create_task(self._call_legacy_shell(event.item.arguments))
                            elif event.item.name in mcp_tools:
                                _mcp_client, _mcp_original_name = mcp_tools[event.item.name]
                                tool_calls[event.item.call_id] = asyncio.create_task(self._call_mcp_tool(_mcp_client, _mcp_original_name, event.item.arguments))
                            else:
                                tool_calls[event.item.call_id] = asyncio.create_task(self._call_tool(event.item))
                        elif isinstance(event.item, ResponseReasoningItem):
                            for summary in event.item.summary:
                                formatter.print_thinking(summary.text)
                        elif isinstance(event.item, ResponseFunctionShellToolCall):
                            for command in event.item.action.commands:
                                if event.item.action.timeout_ms is not None:
                                    tool_name = f"bash (timeout: {event.item.action.timeout_ms / 1000.0}s)"
                                else:
                                    tool_name = "bash"
                                formatter.print_tool_use(tool_name, command)
                            shell_calls[event.item.call_id] = (
                                asyncio.create_task(
                                    self._call_shell(
                                        event.item.action.commands,
                                        event.item.action.timeout_ms,
                                        event.item.action.max_output_length,
                                    )
                                ),
                                event.item,
                            )
                        else:
                            assert False, f"Unexpected item type: {type(event.item)}"

                    elif isinstance(event, (ResponseCompletedEvent, ResponseIncompleteEvent)):
                        response = event.response
                        if response.usage is not None:
                            self.total_token_usage.update(
                                input_tokens_total=response.usage.input_tokens,
                                input_tokens_cached=response.usage.input_tokens_details.cached_tokens,
                                output_tokens=response.usage.output_tokens,
                                model=model,
                                tier=service_tier,
                            )

                        if response.incomplete_details is not None:
                            if response.incomplete_details.reason != "max_output_tokens":
                                raise ResponseIncompleteError(response.incomplete_details.reason)
                            else:
                                logger.warning(f"Output tokens exceeded, compacting conversation")
                                compact_reason = "max_output_tokens"
                    elif isinstance(event, ResponseFunctionCallArgumentsDoneEvent):
                        pass
                    elif isinstance(event, ResponseFunctionCallArgumentsDeltaEvent):
                        pass
                    elif isinstance(event, ResponseAudioDeltaEvent):
                        pass
                    else:
                        pass
            except (APIError, httpx.RemoteProtocolError, httpx.TimeoutException, ResponseIncompleteError) as e:
                if isinstance(e, APIError) and e.code == "context_length_exceeded":
                    logger.warning(f"Context length exceeded, compacting conversation")
                    compact_reason = "context_length_exceeded"
                    continue

                formatter.print_error(f"Request failed with tier {service_tier}: {e}")

                if service_tier == "flex" and compact_reason is None:
                    if last_flex_successful:
                        max_retries = self.max_retries
                    else:
                        max_retries = 0
                else:
                    max_retries = self.max_retries

                if retry < max_retries:
                    backoff = _compute_backoff_time(retry)
                    logger.warning(f"Request failed with tier {service_tier}, retrying... ({retry+1}/{max_retries}) with backoff time {backoff}")
                    await asyncio.sleep(backoff)
                    retry += 1
                    continue
                else:
                    if service_tier == "flex" and compact_reason is None:
                        # reset retries, set flag & switch to standard
                        last_flex_successful = False
                        retry = 0
                        service_tier = "standard"
                        logger.warning(f"Switching to standard tier after {max_retries} retries")
                        continue
                    raise e

            retry = 0
            if service_tier == "flex":
                last_flex_successful = True
            if self.service_tier == "flex":
                service_tier = "flex"

            yield self.total_token_usage.total_cost

            assert response is not None, f"Expected response, got last event: {last_event}"

            # Persist assistant outputs (messages, tool calls, reasoning, ...)
            # so future requests can include complete conversation history.
            self.conversation.extend(
                cast(
                    list[ResponseInputItemParam],
                    [item.model_dump(mode="json", exclude_none=True) for item in response.output],
                )
            )

            if not tool_calls and not shell_calls and compact_reason is None:
                break

            shell_tasks = [task for task, _ in shell_calls.values()]
            await asyncio.gather(*tool_calls.values(), *shell_tasks, return_exceptions=True)

            for call_id, task in tool_calls.items():
                if task.exception() is not None:
                    formatter.print_tool_result(str(task.exception()), True)
                else:
                    formatter.print_tool_result(task.result(), False)

                self.conversation.append(FunctionCallOutput(
                    call_id=call_id,
                    output=json.dumps(str(task.exception()) if task.exception() else task.result()),
                    type="function_call_output",
                ))

            for call_id, (task, shell_call) in shell_calls.items():
                for output in task.result():
                    if output["outcome"]["type"] == "exit":
                        if output["outcome"]["exit_code"] != 0:
                            formatter.print_tool_result(output["stderr"], True)
                        else:
                            formatter.print_tool_result(output["stdout"], False)
                    elif output["outcome"]["type"] == "timeout":
                        formatter.print_tool_result("Shell command timed out", True)
                    else:
                        assert False, f"Unexpected outcome: {output['outcome']}"

                self.conversation.append(ShellCallOutput(
                    call_id=call_id,
                    output=task.result(),
                    type="shell_call_output",
                    max_output_length=shell_call.action.max_output_length,
                ))

    async def query(self, prompt: str, model: str, max_cost: float | None, formatter: VerboseFormatter) -> AsyncIterator[OpenAIResponse]:
        if model.lower() not in GPT_PRICING:
            raise ValueError(f"Model '{model}' not supported")

        if self._session_id is None:
            self._session_id = uuid.uuid4().hex

        mcp_clients = {}
        opened_clients = []

        try:
            for server_name, info in self.mcps.items():
                if isinstance(info, ClientSession):
                    mcp_clients[server_name] = info
                else:
                    if isinstance(info, StdioServerParameters):
                        handle = stdio_client(info)
                    elif isinstance(info, SSEServerParameters):
                        handle = sse_client(info.url, info.headers, info.timeout, info.sse_read_timeout)
                    elif isinstance(info, StreamableHTTPServerParameters):
                        handle = streamablehttp_client(info.url, info.headers, info.timeout, info.sse_read_timeout, info.terminate_on_close)
                    else:
                        raise ValueError(f"Unknown MCP server type: {type(info)}")

                    read, write = await handle.__aenter__()
                    opened_clients.append(handle)

                    # TODO: read timeout seconds
                    client = ClientSession(read, write)
                    opened_clients.append(client)

                    session = await client.__aenter__()
                    await session.initialize()
                    mcp_clients[server_name] = session

            formatter.print_user_message(prompt)

            initial_cost = self.total_token_usage.total_cost

            if max_cost is not None and max_cost <= 0:
                yield OpenAIResponse(cost=0.0, status="terminating_on_max_cost")
                return

            async for total_cost in self._stream_messages(prompt, model, mcp_clients, formatter):
                current_cost = total_cost - initial_cost
                yield OpenAIResponse(cost=current_cost, status="running")
                if max_cost is not None and current_cost >= max_cost:
                    formatter.print_error(f"Max cost reached ({current_cost:.4f} >= {max_cost:.4f}). Stopping query.")
                    yield OpenAIResponse(cost=current_cost, status="terminating_on_max_cost")
                    return

            yield OpenAIResponse(cost=self.total_token_usage.total_cost - initial_cost, status="succeeded")
        finally:
            for client in reversed(opened_clients):
                await client.__aexit__(None, None, None)


    def reset(self) -> None:
        """
        Reset the session ID
        """
        self.conversation = []
        self._session_id = None
