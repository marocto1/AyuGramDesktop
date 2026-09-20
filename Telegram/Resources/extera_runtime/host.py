import argparse
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import types

from base_plugin import BasePlugin
from ui.settings import Divider, Header, Input, Selector, Switch


MAX_SOURCE = 1024 * 1024
MAX_MESSAGE = 2 * 1024 * 1024
ID_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_-]{1,31}\Z")
ANDROID_IMPORTS = ("android", "java", "javax", "org.telegram", "com", "hook_utils",
                   "android_utils", "client_utils", "jnius", "chaquopy")


def atomic_write(path, data):
    temporary = path.with_suffix(path.suffix + ".tmp")
    if path.is_symlink() or temporary.is_symlink():
        raise ValueError("Symbolic links are not supported in plugin storage")
    with temporary.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def inspect_source(source):
    if len(source) > MAX_SOURCE:
        raise ValueError("Plugin exceeds 1 MiB")
    tree = ast.parse(source.decode("utf-8-sig"))
    metadata = {}
    keys = ("id", "name", "description", "author", "version", "icon", "platform",
            "desktop_api", "requirements")
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in (
                    "__" + key + "__" for key in keys
                ):
                    metadata[target.id[2:-2]] = ast.literal_eval(node.value)
    if not isinstance(metadata.get("id"), str) or not ID_PATTERN.fullmatch(metadata["id"]):
        raise ValueError("Plugin id must be 2–32 Latin letters, digits, underscores or hyphens")
    if not isinstance(metadata.get("name"), str) or not metadata["name"].strip():
        raise ValueError("Plugin name is required")
    for key in ("id", "name", "description", "author", "version", "icon"):
        value = metadata.setdefault(key, "1.0" if key == "version" else "")
        if not isinstance(value, str) or len(value) > 4096:
            raise ValueError("Invalid metadata: " + key)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    android = sorted({name for name in imports if any(
        name == prefix or name.startswith(prefix + ".") for prefix in ANDROID_IMPORTS
    )})
    reason = ""
    if android:
        reason = "Android/Java APIs require a Desktop port: " + ", ".join(android)
    elif metadata.get("platform") != "desktop" or metadata.get("desktop_api") != 1:
        reason = 'Desktop plugins require __platform__ = "desktop" and __desktop_api__ = 1'
    elif metadata.get("requirements"):
        reason = "Third-party package installation is not supported by Desktop API 1"
    metadata.update(compatible=not reason, reason=reason,
                    sha256=hashlib.sha256(source).hexdigest())
    return metadata


class Host:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.directory = self.root / "plugins"
        if self.directory.is_symlink():
            raise ValueError("Plugin directory must not be a symbolic link")
        self.directory.mkdir(exist_ok=True)
        self.state_path = self.root / "state.json"
        self.marker = self.root / "running"
        self.state = {"engine": False, "plugins": {}}
        self.active = {}
        self.modules = {}
        self.warning = ""
        self.closed = False
        if self.state_path.exists():
            try:
                if self.state_path.is_symlink() or self.state_path.stat().st_size > MAX_MESSAGE:
                    raise ValueError("Invalid state file")
                state = json.loads(self.state_path.read_text("utf-8"))
                if not isinstance(state, dict) or type(state.get("engine")) is not bool:
                    raise ValueError("Invalid state")
                if not isinstance(state.get("plugins"), dict):
                    raise ValueError("Invalid plugin records")
                for plugin_id, record in state["plugins"].items():
                    if not ID_PATTERN.fullmatch(plugin_id) or not isinstance(record, dict):
                        raise ValueError("Invalid plugin record")
                    if not isinstance(record.get("settings", {}), dict):
                        raise ValueError("Invalid plugin settings")
                self.state = state
            except (ValueError, OSError, TypeError) as error:
                self.warning = "State was not loaded: " + str(error)
                self.state = {"engine": False, "plugins": {}}
        if self.marker.exists():
            self.state["engine"] = False
            self.warning = "Previous plugin host stopped unexpectedly. Engine disabled."
        atomic_write(self.marker, b"running\n")
        if self.state["engine"]:
            for plugin_id, record in self.state["plugins"].items():
                if record.get("enabled"):
                    try:
                        self.load(plugin_id)
                    except Exception as error:
                        record["enabled"] = False
                        record["error"] = str(error)[:2000]
        self.save()

    def path(self, plugin_id):
        if not isinstance(plugin_id, str) or not ID_PATTERN.fullmatch(plugin_id):
            raise ValueError("Invalid plugin id")
        path = self.directory / (plugin_id + ".plugin")
        if path.is_symlink():
            raise ValueError("Symbolic links are not supported")
        return path

    def source(self, plugin_id):
        with self.path(plugin_id).open("rb") as stream:
            return stream.read(MAX_SOURCE + 1)

    def save(self):
        for plugin_id, plugin in self.active.items():
            self.state["plugins"][plugin_id]["settings"] = plugin.export_settings()
        data = json.dumps(self.state, ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(data) > MAX_MESSAGE:
            raise ValueError("Plugin settings exceed storage limit")
        atomic_write(self.state_path, data)

    def load(self, plugin_id):
        if plugin_id in self.active:
            return
        record = self.state["plugins"][plugin_id]
        source = self.source(plugin_id)
        meta = inspect_source(source)
        if not meta["compatible"]:
            raise ValueError(meta["reason"])
        if meta["sha256"] != record["sha256"] or meta["id"] != plugin_id:
            raise ValueError("Plugin file changed. Remove it and import the reviewed file again.")
        module_name = "extera_plugin_" + plugin_id
        module = types.ModuleType(module_name)
        module.__file__ = str(self.path(plugin_id))
        sys.modules[module_name] = module
        try:
            exec(compile(source, module.__file__, "exec"), module.__dict__)
            classes = [value for value in module.__dict__.values()
                       if isinstance(value, type) and value is not BasePlugin
                       and issubclass(value, BasePlugin) and value.__module__ == module.__name__]
            if len(classes) != 1:
                raise ValueError("Define exactly one BasePlugin subclass")
            plugin = classes[0]()
            if not hasattr(plugin, "_settings"):
                raise ValueError("Plugin constructors must call super().__init__()")
            plugin.id = plugin_id
            plugin.import_settings(record.get("settings", {}))
            plugin.on_plugin_load()
            self.active[plugin_id] = plugin
            self.modules[plugin_id] = module_name
            record.pop("error", None)
        except BaseException:
            sys.modules.pop(module_name, None)
            raise

    def unload(self, plugin_id):
        plugin = self.active.pop(plugin_id, None)
        if plugin:
            try:
                plugin.on_plugin_unload()
            except Exception as error:
                self.state["plugins"][plugin_id]["error"] = str(error)[:2000]
            finally:
                self.state["plugins"][plugin_id]["settings"] = plugin.export_settings()
                sys.modules.pop(self.modules.pop(plugin_id, ""), None)

    def snapshot(self):
        plugins = []
        previews = {}
        for plugin_id, record in self.state["plugins"].items():
            try:
                meta = inspect_source(self.source(plugin_id))
                if meta["sha256"] != record.get("sha256") or meta["id"] != plugin_id:
                    meta.update(compatible=False, reason="File changed; remove and reimport")
                    self.unload(plugin_id)
                    record["enabled"] = False
            except (ValueError, OSError, SyntaxError) as error:
                meta = dict(id=plugin_id, name=plugin_id, compatible=False, reason=str(error))
                self.unload(plugin_id)
                record["enabled"] = False
            meta.update(id=plugin_id, enabled=bool(record.get("enabled")),
                        active=plugin_id in self.active, pinned=bool(record.get("pinned")),
                        error=record.get("error", ""))
            if plugin_id in self.active:
                plugin = self.active[plugin_id]
                previews.update(plugin._previews)
                meta["logs"] = plugin._logs
            plugins.append(meta)
        plugins.sort(key=lambda meta: (not meta["pinned"], meta["name"].casefold()))
        return dict(engine=self.state["engine"], plugins=plugins, previews=previews,
                    warning=self.warning, api=1)

    def setting_rows(self, plugin_id):
        if plugin_id not in self.active:
            raise ValueError("Enable the engine and plugin before editing its settings")
        rows = self.active[plugin_id].create_settings()
        if not isinstance(rows, list) or len(rows) > 100:
            raise ValueError("Expected at most 100 settings rows")
        keys = set()
        for row in rows:
            if type(row) not in (Header, Divider, Input, Switch, Selector):
                raise ValueError("Unsupported Desktop setting type")
            if hasattr(row, "key"):
                if not isinstance(row.key, str) or not row.key or row.key in keys:
                    raise ValueError("Settings keys must be non-empty and unique")
                keys.add(row.key)
        return rows

    def settings(self, plugin_id):
        result = []
        plugin = self.active.get(plugin_id)
        for row in self.setting_rows(plugin_id):
            item = {"type": type(row).__name__, "text": str(row.text)}
            if hasattr(row, "key"):
                item.update(key=row.key, value=plugin.get_setting(row.key, row.default))
            if isinstance(row, Selector):
                item["items"] = row.items or []
            if hasattr(row, "subtext"):
                item["subtext"] = row.subtext
            result.append(item)
        return result

    def set_setting(self, plugin_id, key, value):
        rows = self.setting_rows(plugin_id)
        row = next((row for row in rows if getattr(row, "key", None) == key), None)
        if row is None:
            raise ValueError("Unknown setting")
        if isinstance(row, Input) and (not isinstance(value, str) or len(value) > 4096):
            raise ValueError("Expected text of at most 4096 characters")
        if isinstance(row, Switch) and type(value) is not bool:
            raise ValueError("Expected a boolean")
        if isinstance(row, Selector) and (type(value) is not int or not 0 <= value < len(row.items or [])):
            raise ValueError("Invalid selection")
        plugin = self.active[plugin_id]
        previous = plugin.export_settings(), copy.deepcopy(plugin._previews)
        try:
            plugin.set_setting(key, value)
            if row.on_change:
                row.on_change(value)
            self.save()
        except Exception:
            plugin._settings, plugin._previews = previous
            self.save()
            raise

    def dispatch(self, request):
        op = request.get("op")
        plugin_id = request.get("plugin")
        result = {}
        if op == "install":
            path = Path(request["path"])
            if path.suffix.lower() != ".plugin" or path.is_symlink():
                raise ValueError("Choose a regular .plugin file")
            with path.open("rb") as stream:
                source = stream.read(MAX_SOURCE + 1)
            meta = inspect_source(source)
            plugin_id = meta["id"]
            if plugin_id in self.state["plugins"] or self.path(plugin_id).exists():
                raise ValueError("Plugin id already installed; remove it before replacing")
            atomic_write(self.path(plugin_id), source)
            self.state["plugins"][plugin_id] = dict(
                enabled=False, pinned=False, sha256=meta["sha256"], settings={})
        elif op == "engine":
            value = request["value"]
            if type(value) is not bool:
                raise ValueError("Expected a boolean")
            self.state["engine"] = value
            self.warning = ""
            for plugin_id, record in self.state["plugins"].items():
                if value and record.get("enabled"):
                    try:
                        self.load(plugin_id)
                    except Exception as error:
                        record.update(enabled=False, error=str(error)[:2000])
                elif not value:
                    self.unload(plugin_id)
        elif op in ("enable", "pin", "remove", "settings", "set_setting"):
            self.path(plugin_id)
            if plugin_id not in self.state["plugins"]:
                raise ValueError("Plugin is not installed")
            record = self.state["plugins"][plugin_id]
            if op in ("enable", "pin") and type(request.get("value")) is not bool:
                raise ValueError("Expected a boolean")
            if op == "enable":
                if request["value"]:
                    if not self.state["engine"]:
                        raise ValueError("Enable the plugin engine first")
                    try:
                        self.load(plugin_id)
                    except Exception as error:
                        record.update(enabled=False, error=str(error)[:2000])
                        raise
                else:
                    self.unload(plugin_id)
                record["enabled"] = request["value"]
            elif op == "pin":
                record["pinned"] = request["value"]
            elif op == "remove":
                self.unload(plugin_id)
                self.path(plugin_id).unlink(missing_ok=True)
                del self.state["plugins"][plugin_id]
            elif op == "settings":
                result["settings"] = self.settings(plugin_id)
            elif op == "set_setting":
                self.set_setting(plugin_id, request["key"], request["value"])
                result["settings"] = self.settings(plugin_id)
        elif op == "shutdown":
            self.close()
        elif op != "list":
            raise ValueError("Unknown operation")
        result["snapshot"] = self.snapshot()
        self.save()
        return result

    def close(self):
        if self.closed:
            return
        for plugin_id in list(self.active):
            self.unload(plugin_id)
        self.save()
        self.marker.unlink(missing_ok=True)
        self.closed = True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    protocol = sys.stdout
    sys.stdout = sys.stderr
    host = Host(args.root)
    clean_exit = False
    try:
        while True:
            line = sys.stdin.buffer.readline(MAX_MESSAGE + 1)
            if not line:
                clean_exit = True
                break
            request = {}
            try:
                if len(line) > MAX_MESSAGE:
                    raise ValueError("Request exceeds size limit")
                request = json.loads(line)
                if not isinstance(request, dict):
                    request = {}
                    raise ValueError("Request must be an object")
                response = dict(id=request.get("id"), ok=True, **host.dispatch(request))
            except Exception as error:
                response = dict(id=request.get("id"), ok=False, error=str(error)[:2000],
                                snapshot=host.snapshot())
            data = json.dumps(response, ensure_ascii=True, allow_nan=False)
            if len(data) > MAX_MESSAGE:
                raise ValueError("Response exceeds size limit")
            protocol.write(data + "\n")
            protocol.flush()
            if request.get("op") == "shutdown":
                clean_exit = True
                break
    finally:
        if clean_exit:
            host.close()


if __name__ == "__main__":
    main()
