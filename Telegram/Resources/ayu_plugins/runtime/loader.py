"""Runtime loader for exteraGram/AyuGram `.plugin` source files."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from dataclasses import dataclass
from importlib.machinery import SourceFileLoader
from pathlib import Path
from typing import Any

from base_plugin import BasePlugin


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


def create_settings(plugin_id: str) -> list[Any]:
    result = call_hook(plugin_id, "create_settings")
    if result is None:
        return []
    if not isinstance(result, list):
        raise TypeError("create_settings() must return a list")
    return result


def loaded_plugin_ids() -> tuple[str, ...]:
    return tuple(_loaded)
