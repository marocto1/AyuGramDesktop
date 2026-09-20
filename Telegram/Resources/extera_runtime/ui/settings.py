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
    on_long_click: Callable | None = None
    link_alias: str = ""


@dataclass
class Switch:
    key: str
    text: str
    default: bool = False
    icon: str = ""
    subtext: str = ""
    on_change: Callable[[Any], None] | None = None
    on_long_click: Callable | None = None
    link_alias: str = ""


@dataclass
class Selector:
    key: str
    text: str
    default: int = 0
    items: list[str] | None = None
    icon: str = ""
    on_change: Callable[[Any], None] | None = None
    on_long_click: Callable | None = None
    link_alias: str = ""


@dataclass
class Text:
    text: str
    subtext: str = ""
    icon: str = ""
    accent: bool = False
    red: bool = False
    on_click: Callable | None = None
    on_long_click: Callable | None = None
    create_sub_fragment: Callable | None = None
    link_alias: str = ""


@dataclass
class EditText:
    key: str
    hint: str
    default: str = ""
    multiline: bool = False
    max_length: int = 4096
    mask: str = ""
    on_change: Callable[[Any], None] | None = None


@dataclass
class Custom:
    item: Any = None
    view: Any = None
    factory: Any = None
    factory_args: tuple = ()
    on_click: Callable | None = None
    on_long_click: Callable | None = None
    create_sub_fragment: Callable | None = None
    link_alias: str = ""
