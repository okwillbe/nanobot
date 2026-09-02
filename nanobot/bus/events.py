"""Event types for the message bus."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nanobot.bus.outbound_events import OutboundEvent

# Optional ``OutboundMessage.metadata`` key for structured, channel-agnostic UI
# payloads. Value is JSON-serializable with at least ``kind``; rich clients may
# render it and other channels may ignore unknown keys.
OUTBOUND_META_AGENT_UI = "_agent_ui"

# Internal-only inbound metadata used by in-process channels to ask the agent
# loop to update runtime state without going through a user session.
INBOUND_META_RUNTIME_CONTROL = "_runtime_control"
RUNTIME_CONTROL_ACK = "_ack"
RUNTIME_CONTROL_IMAGE_GENERATION_RELOAD = "image_generation_reload"
RUNTIME_CONTROL_SESSION_DISCARD = "session_discard"


@dataclass
class InboundMessage: #在软件架构、网络通信和消息系统中，Inbound 的字面意思是“入站”、“传入”或“进入”。
    """Message received from a chat channel. """

    channel: str  # telegram, discord, slack, whatsapp
    sender_id: str  # User identifier
    chat_id: str  # Chat/channel identifier
    content: str  # Message text
    """@dataclass
     class Message:
    created_at: datetime = datetime.now()  # ❌ 致命错误！ 定义这个类的那一瞬间 只执行一次 """
    timestamp: datetime = field(default_factory=datetime.now) #注意这里的写法：default_factory 接收一个可调用对象（函数），每当 Message() 被实例化时，才会实时调用一次 datetime.now()，生成当前的准确时间戳。传入的是 datetime.now（没有括号），传的是这个工具/函数本身，而不是调用的结果。执行时机：定义类时不执行；每次你执行 Message() 创建新对象时，内部才会自动帮你加上括号调用一次。
    media: list[str] = field(default_factory=list)  # Media URLs
    metadata: dict[str, Any] = field(default_factory=dict)  # Channel-specific data
    session_key_override: str | None = None  # Optional override for thread-scoped sessions
    require_existing_session: bool = False
    """Python（“我们都是成年人” + 统一访问原则）：
    Python 鼓励先直接公开属性（self.name = "Alice"），调用方直接通过 user.name 访问，不需要提前写毫无意义的空套壳 Getter/Setter，并且也不用提前定义name。因为方法名可以直接作为属性名使用"""
    @property #@property 之所以修饰方法而不是字段，核心原因在于：它的本质是一个方法拦截器（Getter/Setter 的语法糖），用于将方法伪装成普通属性
    def session_key(self) -> str:
        """Unique key for session identification. 1. session_key 是「会话」的唯一标识，而不是「单条消息」的唯一标识
同一个会话（Session）里的多轮消息：你在 Telegram 私聊中连续发送 10 条消息，系统会产生 10 个 InboundMessage 实例，但它们的 session_key 完全相同（都是 telegram:123456）。
作用：正因为它们共享同一个 session_key，AgentLoop 才能：
将这 10 轮对话归入同一个上下文记忆（持续多轮对话）；
对同一个会话加锁排队，避免同一用户的多条消息同时调用大模型导致状态冲突。 2. 如果调用时传了 session_key_override（通常由 Session 模块设置），则优先使用；否则使用 channel:chat_id 组合。"""
        return self.session_key_override or f"{self.channel}:{self.chat_id}"


@dataclass
class OutboundMessage:
    """Message to send to a chat channel.

    ``event`` carries internal runtime/UI semantics. ``metadata`` is reserved
    for channel routing context (``message_id``, thread ids, etc.) and optional
    ``OUTBOUND_META_AGENT_UI`` blobs for rich clients.
    """

    channel: str
    chat_id: str
    content: str
    reply_to: str | None = None
    media: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict) #传递给特定渠道的定制私货/上下文路由数据（如 Thread ID、高级卡片配置）。
    buttons: list[list[str]] = field(default_factory=list) #用于在聊天窗口的消息下方渲染可点击的交互式按钮（Inline Buttons）。比如确认弹窗、快速回复选项（Yes / No / Cancel）。
    event: "OutboundEvent | None" = None  #用引号包起来 "OutboundEvent | None"？（核心关键点：解决循环导入）
