"""Typed outbound events carried by :class:`OutboundMessage`.

The message bus still transports :class:`nanobot.bus.events.OutboundMessage`
because channels need chat routing fields. Runtime/UI semantics live on the
message's explicit ``event`` field rather than in reserved metadata flags.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any, cast

from nanobot.bus.events import OutboundMessage

# 在 nanobot/bus/events.py的 OutboundMessage 中，定义了：event: "OutboundEvent | None" = None
class OutboundEvent: # 标记基类 / 标签接口
    """Marker base for internal outbound runtime events."""


@dataclass(frozen=True)  # frozen=True 表示创建后不能修改实例属性
class ProgressEvent(OutboundEvent): #继承类，子类继承父类的属性和方法 （中间进度的消息）展示思考过程（CoT）、工具调用卡片、文件修改 Diff 等（刚才讨论过的核心类）。
    content: str = ""
    tool_hint: bool = False #是否为工具提示。为 True 时表示 content 是工具调用动作，前端通常会将其渲染为卡片、代码块或灰色提示条，而不是正式回答。
    reasoning: bool = False #是否为思考过程。标识内容属于大模型的深度思考 / 思考链（CoT）内容
    reasoning_delta: bool = False #思考增量片段。大模型流式输出思考过程时（如 DeepSeek-R1 / Claude 思维链），每个打字机增量字块会标记为 True。
    reasoning_end: bool = False #思考结束标志。通知前端大模型的思考已结束，前端此时可以自动收起 / 折叠思考面板。
    stream_id: str | None = None #流会话标识。用于前端识别和聚合属于同一个流式输出块的数据。
    tool_events: list[dict[str, Any]] | None = None #结构化工具事件。记录工具执行生命周期（如 {"name": "web_search", "phase": "start" / "end"}），供富客户端渲染工具调用组件。
    file_edit_events: list[dict[str, Any]] | None = None #文件改动事件。包含文件修改的具体 Diff 变更详情，WebUI 客户端可用它直接渲染代码对比视图。


@dataclass(frozen=True) #（重试等待消息）作用：当调用 LLM 遇到网络抖动或被限流（429 Too Many Requests）时，向前端发出提示（如 "请求受限，3秒后重试..."），避免用户以为程序卡死。
class RetryWaitEvent(OutboundEvent):
    content: str = ""


@dataclass(frozen=True) #（流式增量） 大模型生成文字时吐出的每一个小片段（Chunk/字词）。
class StreamDeltaEvent(OutboundEvent):
    content: str = ""
    stream_id: str | None = None


@dataclass(frozen=True) #流式结束 通知前端当前这条流已经完整输出完毕，打字机可以停了。
class StreamEndEvent(OutboundEvent):
    content: str = ""
    stream_id: str | None = None
    resuming: bool = False
    merge_next: bool = False


@dataclass(frozen=True) #（流式响应标记） 一个空标记类，用来告知渠道“本条消息之前已经通过流式方式打完了”，渠道无需重复发送全量文本。
class StreamedResponseEvent(OutboundEvent):
    pass


@dataclass(frozen=True) #本轮回合彻底结束 作用：当前一轮对话完全处理完毕，携带耗时统计（latency_ms）和状态数据，前端可借此停掉加载圈圈并展示总耗时。
class TurnEndEvent(OutboundEvent):
    latency_ms: int | None = None
    goal_state: dict[str, Any] | None = None


@dataclass(frozen=True) #目标状态变更 通知前端长期任务的状态转变（status: 如 "running"、"completed"、"failed"）以及开始时间（started_at）。
class GoalStatusEvent(OutboundEvent):
    status: str
    started_at: float | None = None


@dataclass(frozen=True) #目标状态机同步 作用：同步长期目标的内部状态树（goal_state），前端（如 WebUI）可用它渲染任务看板、待办列表等。
class GoalStateSyncEvent(OutboundEvent):
    goal_state: dict[str, Any]


@dataclass(frozen=True) #会话更新 会话的工作区作用域（scope，如切换了项目目录）发生变化时通知客户端更新。
class SessionUpdatedEvent(OutboundEvent):
    scope: str | None = None


@dataclass(frozen=True) #模型切换通知 作用：用户在聊天中通过指令动态切换了模型（例如从 claude-3-7-sonnet 切换到了 gpt-4o）时广播给前端刷新 UI 显示。
class RuntimeModelUpdatedEvent(OutboundEvent):
    model: str | None
    model_preset: str | None = None


@dataclass(frozen=True) #TurnModelUpdatedEvent 作用：当主力模型遭遇故障时，系统自动 Fallback 到了备用降级模型，通过此事件告诉用户：“本轮对话临时由备用模型 xxx 接管处理”。
class TurnModelUpdatedEvent(OutboundEvent):
    """The fallback model currently handling one chat turn."""

    model: str


def outbound_message_for_event(
    *,
    channel: str,
    chat_id: str,
    event: OutboundEvent,
    content: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> OutboundMessage:
    """Build an :class:`OutboundMessage` for a typed event."""

    return OutboundMessage(
        channel=channel,
        chat_id=chat_id,
        content=_event_content(event) if content is None else content, #三目运算
        event=event,
        metadata=dict(metadata or {}),
    )

#OutboundMessage  转为 event 的方法
def outbound_event_from_message(msg: OutboundMessage) -> OutboundEvent | None:
    """Return the typed outbound event carried by *msg*, if any."""

    if msg.event is not None:
        return msg.event
    return _legacy_event_from_metadata(msg)


def replace_outbound_event(
    msg: OutboundMessage,
    event: OutboundEvent,
    *,
    content: str | None = None,
) -> OutboundMessage:
    """Return *msg* with a new event and optional content."""

    return replace(
        msg,
        content=_event_content(event) if content is None else content,
        event=event,
    )


def _event_content(event: OutboundEvent) -> str:
    if isinstance(event, ProgressEvent | RetryWaitEvent | StreamDeltaEvent | StreamEndEvent):
        return event.content
    return ""


def _legacy_event_from_metadata(msg: OutboundMessage) -> OutboundEvent | None:
    """Bridge pre-typed outbound metadata flags into typed events.

    New code should set ``OutboundMessage.event`` directly. The fallback keeps
    older in-process extensions and channel plugins from losing runtime events
    while they migrate off reserved metadata flags.
    """

    meta = msg.metadata or {}
    if meta.get("_runtime_model_updated"):
        return RuntimeModelUpdatedEvent(
            model=_metadata_str(meta, "model"),
            model_preset=_metadata_str(meta, "model_preset"),
        )
    if meta.get("_goal_state_sync"):
        goal_state = meta.get("goal_state")
        return GoalStateSyncEvent(
            cast(dict[str, Any], goal_state)
            if isinstance(goal_state, dict)
            else {"active": False}
        )
    if meta.get("_goal_status"):
        status = meta.get("goal_status")
        if not isinstance(status, str) or not status:
            return None
        return GoalStatusEvent(
            status=status,
            started_at=_metadata_float(meta, "started_at", "goal_started_at"),
        )
    if meta.get("_turn_end"):
        goal_state = meta.get("goal_state")
        return TurnEndEvent(
            latency_ms=_metadata_int(meta, "latency_ms"),
            goal_state=cast(dict[str, Any], goal_state) if isinstance(goal_state, dict) else None,
        )
    if meta.get("_session_updated"):
        return SessionUpdatedEvent(scope=_metadata_str(meta, "_session_update_scope"))
    if meta.get("_retry_wait"):
        return RetryWaitEvent(content=msg.content)
    if meta.get("_stream_end"):
        return StreamEndEvent(
            content=msg.content,
            stream_id=_metadata_str(meta, "_stream_id"),
            resuming=bool(meta.get("_resuming")),
            merge_next=bool(meta.get("_merge_next")),
        )
    if meta.get("_stream_delta"):
        return StreamDeltaEvent(
            content=msg.content,
            stream_id=_metadata_str(meta, "_stream_id"),
        )
    if meta.get("_streamed"):
        return StreamedResponseEvent()
    if (
        meta.get("_progress")
        or meta.get("_reasoning_delta")
        or meta.get("_reasoning_end")
        or meta.get("_reasoning")
        or meta.get("_file_edit_events")
        or meta.get("_tool_events")
    ):
        tool_events = meta.get("_tool_events")
        file_edit_events = meta.get("_file_edit_events")
        return ProgressEvent(
            content=msg.content,
            tool_hint=bool(meta.get("_tool_hint")),
            reasoning=bool(meta.get("_reasoning")),
            reasoning_delta=bool(meta.get("_reasoning_delta")),
            reasoning_end=bool(meta.get("_reasoning_end")),
            stream_id=_metadata_str(meta, "_stream_id"),
            tool_events=cast(list[dict[str, Any]], tool_events)
            if isinstance(tool_events, list)
            else None,
            file_edit_events=cast(list[dict[str, Any]], file_edit_events)
            if isinstance(file_edit_events, list)
            else None,
        )
    return None


def _metadata_str(meta: Mapping[str, Any], key: str) -> str | None:
    value = meta.get(key)
    return value if isinstance(value, str) and value else None


def _metadata_int(meta: Mapping[str, Any], key: str) -> int | None:
    value = meta.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _metadata_float(meta: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = meta.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int | float):
            return float(value)
    return None
