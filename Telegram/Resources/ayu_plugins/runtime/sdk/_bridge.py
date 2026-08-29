"""Internal bridge used by the clean-room Desktop compatibility SDK."""

from __future__ import annotations

from typing import Any, Callable

try:
    import _ayugram_desktop as _native
except ImportError:
    _native = None


class DesktopBridgeUnavailable(RuntimeError):
    pass


class DesktopUnsupportedApi(RuntimeError):
    pass


def available() -> bool:
    return _native is not None


def _require_native() -> Any:
    if _native is None:
        raise DesktopBridgeUnavailable(
            "AyuGram Desktop native plugin bridge is not loaded"
        )
    return _native


def get_setting(plugin_id: str, key: str, default: Any = None) -> Any:
    if _native is None:
        return default
    return _native.get_setting(plugin_id, key, default)


def set_setting(
    plugin_id: str,
    key: str,
    value: Any,
    reload_settings: bool = False,
) -> Any:
    return _require_native().set_setting(
        plugin_id,
        key,
        value,
        reload_settings,
    )


def log(plugin_id: str, message: object) -> None:
    text = str(message)
    if _native is None:
        print(f"[{plugin_id}] {text}")
        return
    _native.log(plugin_id, text)


def register_hook(
    plugin_id: str,
    name: str,
    match_substring: str | None = None,
    priority: int = 0,
) -> Any:
    return _require_native().register_hook(
        plugin_id,
        name,
        match_substring,
        priority,
    )


def register_send_message_hook(plugin_id: str, priority: int = 0) -> Any:
    return _require_native().register_send_message_hook(plugin_id, priority)


def remove_hook(plugin_id: str, name: str) -> Any:
    return _require_native().remove_hook(plugin_id, name)


def add_menu_item(plugin_id: str, data: Any) -> Any:
    return _require_native().add_menu_item(plugin_id, data)


def remove_menu_item(plugin_id: str, item_id: str) -> Any:
    return _require_native().remove_menu_item(plugin_id, item_id)


def client_call(name: str, *args: Any, **kwargs: Any) -> Any:
    return _require_native().client_call(name, args, kwargs)


def ui_call(name: str, *args: Any, **kwargs: Any) -> Any:
    return _require_native().ui_call(name, args, kwargs)


def hook_call(name: str, *args: Any, **kwargs: Any) -> Any:
    native = _require_native()
    if not hasattr(native, "hook_call"):
        raise DesktopUnsupportedApi(
            f"Android/Java hook API '{name}' is not supported on Desktop"
        )
    return native.hook_call(name, args, kwargs)


def run_on_ui_thread(callback: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    if _native is None:
        return callback(*args, **kwargs)
    return _native.run_on_ui_thread(callback, args, kwargs)
