"""Clean-room Desktop implementation of the portable BasePlugin API."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

import _bridge


class HookStrategy(Enum):
    DEFAULT = 0
    CANCEL = 1
    MODIFY = 2
    MODIFY_FINAL = 3


@dataclass
class HookResult:
    strategy: HookStrategy = HookStrategy.DEFAULT
    request: Any = None
    response: Any = None
    update: Any = None
    updates: Any = None
    error: Any = None
    params: Any = None


@dataclass
class PluginMetadata:
    name: str = ""
    description: str = ""
    author: str = ""
    version: str = ""
    icon: str = ""
    min_version: str = ""
    requirements: list[str] = field(default_factory=list)


class PluginError(RuntimeError):
    def __init__(self, plugin_id: str, message: str) -> None:
        self.plugin_id = plugin_id
        self.message = message
        super().__init__(f"[{plugin_id}] {message}")


class AppEvent(Enum):
    APP_START = 1
    START = 1
    APP_STOP = 2
    STOP = 2
    APP_PAUSE = 3
    PAUSE = 3
    APP_RESUME = 4
    RESUME = 4


class MenuItemType(Enum):
    MESSAGE_CONTEXT_MENU = 1
    DRAWER_MENU = 2
    CHAT_ACTION_MENU = 3
    PROFILE_ACTION_MENU = 4


MenuItemTypes = MenuItemType


@dataclass
class MenuItemData:
    menu_type: MenuItemType
    text: str
    on_click: Callable[..., Any] | None = None
    item_id: str | None = None
    subtext: str | None = None
    icon: Any = None
    condition: Callable[..., bool] | None = None
    priority: int = 0


@dataclass
class HookFilterData:
    filter_type: str
    arg_index: int | None = None
    value: Any = None
    or_filters: list[Any] | None = None
    mvel_expression: str | None = None
    instance_of: Any = None


class HookFilter:
    @staticmethod
    def ResultIsInstanceOf(clazz: Any) -> HookFilterData:
        return HookFilterData("RESULT_IS_INSTANCE_OF", instance_of=clazz)

    @staticmethod
    def ResultEqual(value: Any) -> HookFilterData:
        return HookFilterData("RESULT_EQUAL", value=value)

    @staticmethod
    def ResultNotEqual(value: Any) -> HookFilterData:
        return HookFilterData("RESULT_NOT_EQUAL", value=value)

    @staticmethod
    def ArgumentIsNull(index: int) -> HookFilterData:
        return HookFilterData("ARGUMENT_IS_NULL", arg_index=index)

    @staticmethod
    def ArgumentIsTrue(index: int) -> HookFilterData:
        return HookFilterData("ARGUMENT_IS_TRUE", arg_index=index)

    @staticmethod
    def ArgumentIsFalse(index: int) -> HookFilterData:
        return HookFilterData("ARGUMENT_IS_FALSE", arg_index=index)

    @staticmethod
    def ArgumentNotNull(index: int) -> HookFilterData:
        return HookFilterData("ARGUMENT_NOT_NULL", arg_index=index)

    @staticmethod
    def ArgumentIsInstanceOf(index: int, clazz: Any) -> HookFilterData:
        return HookFilterData(
            "ARGUMENT_IS_INSTANCE_OF",
            arg_index=index,
            instance_of=clazz,
        )

    @staticmethod
    def ArgumentEqual(index: int, value: Any) -> HookFilterData:
        return HookFilterData("ARGUMENT_EQUAL", arg_index=index, value=value)


class HookFilterTypes:
    RESULT_IS_INSTANCE_OF = "RESULT_IS_INSTANCE_OF"
    RESULT_EQUAL = "RESULT_EQUAL"
    RESULT_NOT_EQUAL = "RESULT_NOT_EQUAL"
    ARGUMENT_IS_NULL = "ARGUMENT_IS_NULL"
    ARGUMENT_IS_TRUE = "ARGUMENT_IS_TRUE"
    ARGUMENT_IS_FALSE = "ARGUMENT_IS_FALSE"
    ARGUMENT_NOT_NULL = "ARGUMENT_NOT_NULL"
    ARGUMENT_IS_INSTANCE_OF = "ARGUMENT_IS_INSTANCE_OF"
    ARGUMENT_EQUAL = "ARGUMENT_EQUAL"


def fn_hook_filters(*filters: HookFilterData):
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        setattr(func, "__hook_filters__", list(filters))
        return func

    return decorator


class BaseHook:
    def __init__(
        self,
        before: Callable[..., Any] | None = None,
        after: Callable[..., Any] | None = None,
        before_filters: list[HookFilterData] | None = None,
        after_filters: list[HookFilterData] | None = None,
        plugin: Any = None,
    ) -> None:
        self.before = before
        self.after = after
        self.before_filters = before_filters or []
        self.after_filters = after_filters or []
        self.plugin = plugin

    def before_hooked_method(self, param: Any) -> Any:
        if self.before is not None:
            return self.before(param)
        return None

    def after_hooked_method(self, param: Any) -> Any:
        if self.after is not None:
            return self.after(param)
        return None


class MethodHook(BaseHook):
    pass


class MethodReplacement:
    def __init__(self, py_callable: Callable[..., Any]) -> None:
        self.py_callable = py_callable

    def replace_hooked_method(self, param: Any) -> Any:
        return self.py_callable(param)


@dataclass
class XposedHook:
    member: Any = None
    hook: Any = None


def _plugin_id(instance: object) -> str:
    direct = getattr(instance, "_ayu_plugin_id", None)
    if isinstance(direct, str) and direct:
        return direct

    module = sys.modules.get(instance.__class__.__module__)
    value = getattr(module, "__id__", None) if module is not None else None
    if isinstance(value, str) and value:
        return value
    return instance.__class__.__module__


class BasePlugin:
    def on_plugin_load(self) -> None:
        pass

    def on_plugin_unload(self) -> None:
        pass

    def create_settings(self) -> list[Any]:
        return []

    def on_app_event(self, event_type: Any) -> Any:
        return None

    def pre_request_hook(
        self,
        request_name: str,
        account: Any,
        request: Any,
    ) -> Any:
        return None

    def post_request_hook(
        self,
        request_name: str,
        account: Any,
        response: Any,
        error: Any,
    ) -> Any:
        return None

    def on_update_hook(
        self,
        update_name: str,
        account: Any,
        update: Any,
    ) -> Any:
        return None

    def on_updates_hook(
        self,
        container_name: str,
        account: Any,
        updates: Any,
    ) -> Any:
        return None

    def on_send_message_hook(self, account: Any, params: Any) -> Any:
        return None

    def add_hook(
        self,
        name: str,
        match_substring: str | None = None,
        priority: int = 0,
    ) -> Any:
        return _bridge.register_hook(
            _plugin_id(self),
            name,
            match_substring,
            priority,
        )

    def add_on_send_message_hook(self, priority: int = 0) -> Any:
        return _bridge.register_send_message_hook(_plugin_id(self), priority)

    def remove_hook(self, name: str) -> Any:
        return _bridge.remove_hook(_plugin_id(self), name)

    def get_setting(self, key: str, default: Any = None) -> Any:
        return _bridge.get_setting(_plugin_id(self), key, default)

    def set_setting(
        self,
        key: str,
        value: Any,
        reload_settings: bool = False,
    ) -> Any:
        return _bridge.set_setting(
            _plugin_id(self),
            key,
            value,
            reload_settings,
        )

    def export_settings(self) -> Any:
        return _bridge.client_call("export_plugin_settings", _plugin_id(self))

    def import_settings(
        self,
        settings: Any,
        reload_settings: bool = False,
    ) -> Any:
        return _bridge.client_call(
            "import_plugin_settings",
            _plugin_id(self),
            settings,
            reload_settings,
        )

    def hook_method(self, *args: Any, **kwargs: Any) -> Any:
        return _bridge.hook_call("hook_method", *args, **kwargs)

    def hook_all_methods(self, *args: Any, **kwargs: Any) -> Any:
        return _bridge.hook_call("hook_all_methods", *args, **kwargs)

    def hook_all_constructors(self, *args: Any, **kwargs: Any) -> Any:
        return _bridge.hook_call("hook_all_constructors", *args, **kwargs)

    def unhook_method(self, *args: Any, **kwargs: Any) -> Any:
        return _bridge.hook_call("unhook_method", *args, **kwargs)

    def add_menu_item(self, menu_item_data: Any) -> Any:
        return _bridge.add_menu_item(_plugin_id(self), menu_item_data)

    def remove_menu_item(self, item_id: str) -> Any:
        return _bridge.remove_menu_item(_plugin_id(self), item_id)

    def log(self, message: object) -> None:
        _bridge.log(_plugin_id(self), message)
