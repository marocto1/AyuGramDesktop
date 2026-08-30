"""Runtime loader for exteraGram/AyuGram `.plugin` source files."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
import traceback
from dataclasses import dataclass
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from base_plugin import BasePlugin, HookStrategy


@dataclass
class _LoadedPlugin:
    plugin_id: str
    path: str
    module_key: str
    module: Any
    instance: BasePlugin


_loaded: dict[str, _LoadedPlugin] = {}


class PluginLoadError(RuntimeError):
    pass


def _module_key(path: str) -> str:
    digest = hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]
    return f"_ayu_plugin_{digest}"


def _find_plugin_class(module: Any, internal_module_name: str) -> type[BasePlugin]:
    candidates: list[type[BasePlugin]] = []
    fallback: list[type[BasePlugin]] = []
    declared_module_name = getattr(module, "__name__", internal_module_name)

    for value in vars(module).values():
        if not isinstance(value, type) or value is BasePlugin:
            continue
        try:
            if not issubclass(value, BasePlugin):
                continue
        except TypeError:
            continue

        fallback.append(value)
        if getattr(value, "__module__", None) in {
            internal_module_name,
            declared_module_name,
        }:
            candidates.append(value)

    pool = candidates or fallback
    if not pool:
        raise PluginLoadError("No BasePlugin subclass found")

    for candidate in pool:
        if candidate.__name__ in {"Plugin", "MainPlugin"}:
            return candidate

    return pool[0]


def load_plugin(path: str) -> dict[str, Any]:
    resolved = str(Path(path).expanduser().resolve())
    if not Path(resolved).is_file():
        raise PluginLoadError(f"Plugin file does not exist: {resolved}")

    key = _module_key(resolved)
    loader = SourceFileLoader(key, resolved)
    spec = importlib.util.spec_from_loader(key, loader)
    if spec is None:
        raise PluginLoadError(f"Could not create module spec for {resolved}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[key] = module

    try:
        loader.exec_module(module)
        plugin_id = getattr(module, "__id__", "")
        if not isinstance(plugin_id, str) or not plugin_id:
            raise PluginLoadError("Plugin has no valid __id__ metadata")
        if plugin_id in _loaded:
            raise PluginLoadError(f"Plugin '{plugin_id}' is already loaded")

        plugin_class = _find_plugin_class(module, key)
        plugin_class.__module__ = key
        instance = plugin_class()
        setattr(instance, "_ayu_plugin_id", plugin_id)
        setattr(instance, "_ayu_plugin_path", resolved)

        loaded = _LoadedPlugin(
            plugin_id=plugin_id,
            path=resolved,
            module_key=key,
            module=module,
            instance=instance,
        )
        _loaded[plugin_id] = loaded

        try:
            instance.on_plugin_load()
        except Exception:
            _loaded.pop(plugin_id, None)
            raise

        return {
            "id": plugin_id,
            "name": getattr(module, "__name__", plugin_id),
            "description": getattr(module, "__description__", ""),
            "author": getattr(module, "__author__", ""),
            "version": getattr(module, "__version__", "1.0"),
            "min_version": getattr(module, "__min_version__", ""),
            "requirements": getattr(module, "__requirements__", ""),
        }
    except Exception:
        sys.modules.pop(key, None)
        raise


def unload_plugin(plugin_id: str) -> None:
    loaded = _loaded.pop(plugin_id, None)
    if loaded is None:
        return
    try:
        loaded.instance.on_plugin_unload()
    finally:
        sys.modules.pop(loaded.module_key, None)


def unload_all() -> None:
    for plugin_id in list(_loaded):
        unload_plugin(plugin_id)


def call_hook(plugin_id: str, hook_name: str, *args: Any, **kwargs: Any) -> Any:
    loaded = _loaded.get(plugin_id)
    if loaded is None:
        raise KeyError(f"Plugin '{plugin_id}' is not loaded")
    hook = getattr(loaded.instance, hook_name, None)
    if hook is None or not callable(hook):
        return None
    return hook(*args, **kwargs)


def _message_from_params(params: Any) -> str:
    message = getattr(params, "message", None)
    if not isinstance(message, str):
        raise TypeError("send message hook params.message must be a string")
    return message


def dispatch_send_message(account: int, message: str) -> dict[str, Any]:
    params: Any = SimpleNamespace(message=message)

    for loaded in tuple(_loaded.values()):
        previous_params = params
        previous_message = _message_from_params(params)
        try:
            result = loaded.instance.on_send_message_hook(account, params)
            strategy = (
                result
                if isinstance(result, HookStrategy)
                else getattr(result, "strategy", HookStrategy.DEFAULT)
            )

            if strategy == HookStrategy.CANCEL:
                return {
                    "cancelled": True,
                    "message": _message_from_params(params),
                }

            if strategy in {HookStrategy.MODIFY, HookStrategy.MODIFY_FINAL}:
                result_params = getattr(result, "params", None)
                if result_params is not None:
                    params = result_params
                _message_from_params(params)

                if strategy == HookStrategy.MODIFY_FINAL:
                    break
        except Exception:
            params = previous_params
            setattr(params, "message", previous_message)
            print(
                f"[AyuPlugins] send message hook failed for {loaded.plugin_id}",
                file=sys.stderr,
            )
            traceback.print_exc()

    return {
        "cancelled": False,
        "message": _message_from_params(params),
    }


def create_settings(plugin_id: str) -> list[Any]:
    result = call_hook(plugin_id, "create_settings")
    if result is None:
        return []
    if not isinstance(result, list):
        raise TypeError("create_settings() must return a list")
    return result


def loaded_plugin_ids() -> tuple[str, ...]:
    return tuple(_loaded)
