"""Declarative settings objects compatible with Android `.plugin` imports."""

from __future__ import annotations

from typing import Any


class SettingItem:
    kind = "setting"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = dict(kwargs)
        for key, value in kwargs.items():
            setattr(self, key, value)

    def to_payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "args": self.args,
            **self.kwargs,
        }

    def __repr__(self) -> str:
        fields = ", ".join(f"{key}={value!r}" for key, value in self.kwargs.items())
        return f"{type(self).__name__}({fields})"


class Switch(SettingItem):
    kind = "switch"


class Selector(SettingItem):
    kind = "selector"


class Input(SettingItem):
    kind = "input"


class Text(SettingItem):
    kind = "text"


class Header(SettingItem):
    kind = "header"


class Divider(SettingItem):
    kind = "divider"


class EditText(SettingItem):
    kind = "edit_text"


class Custom(SettingItem):
    kind = "custom"


def __getattr__(name: str) -> type[SettingItem]:
    if name.startswith("_"):
        raise AttributeError(name)
    return type(name, (SettingItem,), {"kind": name.lower()})
