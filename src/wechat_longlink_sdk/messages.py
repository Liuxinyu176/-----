from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    RICH_MEDIA = "rich_media"
    EVENT = "event"


@dataclass(frozen=True)
class BaseMessage:
    message_type: MessageType
    message_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "type": self.message_type.value,
            "message_id": self.message_id,
            "timestamp": self.timestamp,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class TextMessage(BaseMessage):
    content: str = ""

    def __init__(
        self,
        content: str,
        message_id: str | None = None,
        timestamp: float | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        if not content or not content.strip():
            raise ValueError("text message content is required")
        super().__init__(
            message_type=MessageType.TEXT,
            message_id=message_id or uuid.uuid4().hex,
            timestamp=timestamp if timestamp is not None else time.time(),
            metadata=dict(metadata or {}),
        )
        object.__setattr__(self, "content", content)

    def to_payload(self) -> dict[str, Any]:
        payload = super().to_payload()
        payload["content"] = self.content
        return payload


@dataclass(frozen=True)
class ImageMessage(BaseMessage):
    image_url: str = ""
    caption: str | None = None

    def __init__(
        self,
        image_url: str,
        caption: str | None = None,
        message_id: str | None = None,
        timestamp: float | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        if not image_url or not image_url.strip():
            raise ValueError("image_url is required")
        super().__init__(
            message_type=MessageType.IMAGE,
            message_id=message_id or uuid.uuid4().hex,
            timestamp=timestamp if timestamp is not None else time.time(),
            metadata=dict(metadata or {}),
        )
        object.__setattr__(self, "image_url", image_url)
        object.__setattr__(self, "caption", caption)

    def to_payload(self) -> dict[str, Any]:
        payload = super().to_payload()
        payload["image_url"] = self.image_url
        payload["caption"] = self.caption
        return payload


@dataclass(frozen=True)
class FileMessage(BaseMessage):
    file_name: str = ""
    file_url: str = ""
    file_size: int | None = None
    mime_type: str | None = None

    def __init__(
        self,
        file_name: str,
        file_url: str,
        file_size: int | None = None,
        mime_type: str | None = None,
        message_id: str | None = None,
        timestamp: float | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        if not file_name or not file_name.strip():
            raise ValueError("file_name is required")
        if not file_url or not file_url.strip():
            raise ValueError("file_url is required")
        if file_size is not None and file_size < 0:
            raise ValueError("file_size must be greater than or equal to 0")
        super().__init__(
            message_type=MessageType.FILE,
            message_id=message_id or uuid.uuid4().hex,
            timestamp=timestamp if timestamp is not None else time.time(),
            metadata=dict(metadata or {}),
        )
        object.__setattr__(self, "file_name", file_name)
        object.__setattr__(self, "file_url", file_url)
        object.__setattr__(self, "file_size", file_size)
        object.__setattr__(self, "mime_type", mime_type)

    def to_payload(self) -> dict[str, Any]:
        payload = super().to_payload()
        payload["file_name"] = self.file_name
        payload["file_url"] = self.file_url
        payload["file_size"] = self.file_size
        payload["mime_type"] = self.mime_type
        return payload


@dataclass(frozen=True)
class RichMediaMessage(BaseMessage):
    title: str = ""
    description: str = ""
    resource_url: str = ""
    thumbnail_url: str | None = None

    def __init__(
        self,
        title: str,
        description: str,
        resource_url: str,
        thumbnail_url: str | None = None,
        message_id: str | None = None,
        timestamp: float | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        if not title or not title.strip():
            raise ValueError("title is required")
        if not description or not description.strip():
            raise ValueError("description is required")
        if not resource_url or not resource_url.strip():
            raise ValueError("resource_url is required")
        super().__init__(
            message_type=MessageType.RICH_MEDIA,
            message_id=message_id or uuid.uuid4().hex,
            timestamp=timestamp if timestamp is not None else time.time(),
            metadata=dict(metadata or {}),
        )
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "resource_url", resource_url)
        object.__setattr__(self, "thumbnail_url", thumbnail_url)

    def to_payload(self) -> dict[str, Any]:
        payload = super().to_payload()
        payload["title"] = self.title
        payload["description"] = self.description
        payload["resource_url"] = self.resource_url
        payload["thumbnail_url"] = self.thumbnail_url
        return payload


@dataclass(frozen=True)
class EventMessage(BaseMessage):
    event_name: str = ""
    event_data: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        event_name: str,
        event_data: Mapping[str, Any] | None = None,
        message_id: str | None = None,
        timestamp: float | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        if not event_name or not event_name.strip():
            raise ValueError("event_name is required")
        super().__init__(
            message_type=MessageType.EVENT,
            message_id=message_id or uuid.uuid4().hex,
            timestamp=timestamp if timestamp is not None else time.time(),
            metadata=dict(metadata or {}),
        )
        object.__setattr__(self, "event_name", event_name)
        object.__setattr__(self, "event_data", dict(event_data or {}))

    def to_payload(self) -> dict[str, Any]:
        payload = super().to_payload()
        payload["event_name"] = self.event_name
        payload["event_data"] = dict(self.event_data)
        return payload


_MESSAGE_TYPE_TO_CLASS: dict[MessageType, type[BaseMessage]] = {
    MessageType.TEXT: TextMessage,
    MessageType.IMAGE: ImageMessage,
    MessageType.FILE: FileMessage,
    MessageType.RICH_MEDIA: RichMediaMessage,
    MessageType.EVENT: EventMessage,
}


def register_message_type(message_type: MessageType, message_class: type[BaseMessage]) -> None:
    _MESSAGE_TYPE_TO_CLASS[message_type] = message_class


def message_from_payload(payload: Mapping[str, Any]) -> BaseMessage:
    message_type_value = payload.get("type")
    if not message_type_value:
        raise ValueError("message payload missing type")
    message_type = MessageType(message_type_value)
    message_class = _MESSAGE_TYPE_TO_CLASS.get(message_type)
    if message_class is None:
        raise ValueError(f"unsupported message type: {message_type.value}")
    common_kwargs = {
        "message_id": payload.get("message_id"),
        "timestamp": payload.get("timestamp"),
        "metadata": payload.get("metadata", {}),
    }
    if message_class is TextMessage:
        return TextMessage(content=str(payload.get("content", "")), **common_kwargs)
    if message_class is ImageMessage:
        return ImageMessage(
            image_url=str(payload.get("image_url", "")),
            caption=payload.get("caption"),
            **common_kwargs,
        )
    if message_class is FileMessage:
        return FileMessage(
            file_name=str(payload.get("file_name", "")),
            file_url=str(payload.get("file_url", "")),
            file_size=payload.get("file_size"),
            mime_type=payload.get("mime_type"),
            **common_kwargs,
        )
    if message_class is RichMediaMessage:
        return RichMediaMessage(
            title=str(payload.get("title", "")),
            description=str(payload.get("description", "")),
            resource_url=str(payload.get("resource_url", "")),
            thumbnail_url=payload.get("thumbnail_url"),
            **common_kwargs,
        )
    if message_class is EventMessage:
        event_data = payload.get("event_data", {})
        event_mapping = event_data if isinstance(event_data, Mapping) else {}
        return EventMessage(
            event_name=str(payload.get("event_name", "")),
            event_data=event_mapping,
            **common_kwargs,
        )
    message_kwargs = {key: value for key, value in payload.items() if key != "type"}
    return message_class(message_type=message_type, **message_kwargs)
