from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class Header:
    text: str


@dataclass
class Divider:
    text: str = ""


@dataclass
class Input:
    key: str
    text: str
    default: str = ""
    icon: str = ""
    subtext: str = ""
    on_change: Callable[[Any], None] | None = None


@dataclass
class Switch:
    key: str
    text: str
    default: bool = False
    icon: str = ""
    subtext: str = ""
    on_change: Callable[[Any], None] | None = None


@dataclass
class Selector:
    key: str
    text: str
    default: int = 0
    items: list[str] | None = None
    icon: str = ""
    on_change: Callable[[Any], None] | None = None
