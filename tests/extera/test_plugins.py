import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "Telegram/Resources/extera_runtime"
sys.path.insert(0, str(RUNTIME))
from base_plugin import BasePlugin
from host import Host, MAX_SOURCE, inspect_source

EXAMPLE = ROOT / "plugins/examples/feel_rich_desktop.plugin"


class PluginTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.host = Host(self.root / "state")
        self.addCleanup(lambda: self.host.close())

    def install(self, path=EXAMPLE):
        return self.host.dispatch(dict(op="install", path=str(path)))

    def enable(self):
        self.install()
        self.host.dispatch(dict(op="engine", value=True))
        self.host.dispatch(dict(op="enable", plugin="feel_rich_desktop", value=True))

    def make_plugin(self, text):
        path = self.root / "test.plugin"
        path.write_text(text, encoding="utf-8")
        return path

    def test_metadata(self):
        meta = inspect_source(EXAMPLE.read_bytes())
        self.assertTrue(meta["compatible"])
        self.assertEqual(meta["id"], "feel_rich_desktop")
        self.assertEqual(len(meta["sha256"]), 64)

    def test_inspection_and_install_never_execute(self):
        path = self.make_plugin('__id__="noop"\n__name__="Noop"\nraise RuntimeError("executed")')
        self.install(path)
        self.assertFalse(self.host.snapshot()["plugins"][0]["enabled"])

    def test_android_import_detected_before_execution(self):
        path = self.make_plugin('__id__="android_plugin"\n__name__="Android"\n'
                                'from java.lang import Boolean\nraise RuntimeError("executed")')
        self.install(path)
        meta = self.host.snapshot()["plugins"][0]
        self.assertFalse(meta["compatible"])
        self.assertIn("java.lang", meta["reason"])

    def test_requires_explicit_desktop_api(self):
        meta = inspect_source(b'__id__="legacy"\n__name__="Legacy"')
        self.assertFalse(meta["compatible"])

    def test_path_traversal_id_rejected(self):
        for plugin_id in ("../outside", "x/y", "x\\y", "x", "0x", "x" * 33):
            with self.subTest(plugin_id=plugin_id), self.assertRaises(ValueError):
                inspect_source(f'__id__={plugin_id!r}\n__name__="x"'.encode())

    def test_dynamic_metadata_rejected(self):
        with self.assertRaises(ValueError):
            inspect_source(b'__id__=str("dynamic")\n__name__="x"')

    def test_oversized_source_rejected(self):
        with self.assertRaises(ValueError):
            inspect_source(b" " * (MAX_SOURCE + 1))

    def test_import_starts_disabled(self):
        self.install()
        state = self.host.snapshot()
        self.assertFalse(state["engine"])
        self.assertFalse(state["plugins"][0]["enabled"])
        self.assertEqual(state["previews"], {})

    def test_duplicate_does_not_overwrite(self):
        self.install()
        before = self.host.source("feel_rich_desktop")
        with self.assertRaises(ValueError):
            self.install()
        self.assertEqual(self.host.source("feel_rich_desktop"), before)

    def test_engine_must_be_enabled(self):
        self.install()
        with self.assertRaises(ValueError):
            self.host.dispatch(dict(op="enable", plugin="feel_rich_desktop", value=True))

    def test_lifecycle_and_previews(self):
        self.enable()
        self.assertEqual(self.host.snapshot()["previews"], {"stars": "1000", "ton": "10"})
        self.host.dispatch(dict(op="enable", plugin="feel_rich_desktop", value=False))
        self.assertEqual(self.host.snapshot()["previews"], {})
        self.assertEqual(self.host.active, {})

    def test_settings_callback(self):
        self.enable()
        result = self.host.dispatch(dict(op="set_setting", plugin="feel_rich_desktop",
                                         key="stars_amount", value="42.000000001"))
        self.assertEqual(result["snapshot"]["previews"]["stars"], "42.000000001")
        self.assertEqual(result["settings"][1]["value"], "42.000000001")

    def test_invalid_amount_transaction(self):
        self.enable()
        for value in ("-1", "NaN", "Infinity", "10000000001", "0.0000000001", "bad"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.host.dispatch(dict(op="set_setting", plugin="feel_rich_desktop",
                                        key="stars_amount", value=value))
            self.assertEqual(self.host.snapshot()["previews"]["stars"], "1000")
            self.assertEqual(self.host.settings("feel_rich_desktop")[1]["value"], "1000")

    def test_unknown_setting_and_wrong_type(self):
        self.enable()
        for key, value in (("unknown", "1"), ("stars_amount", 42)):
            with self.assertRaises(ValueError):
                self.host.dispatch(dict(op="set_setting", plugin="feel_rich_desktop",
                                        key=key, value=value))

    def test_engine_off_unloads_all(self):
        self.enable()
        self.host.dispatch(dict(op="engine", value=False))
        self.assertEqual(self.host.snapshot()["previews"], {})
        self.assertTrue(self.host.snapshot()["plugins"][0]["enabled"])
        self.host.dispatch(dict(op="engine", value=True))
        self.assertEqual(self.host.snapshot()["previews"]["stars"], "1000")

    def test_clean_restart_restores_state(self):
        self.enable()
        self.host.dispatch(dict(op="set_setting", plugin="feel_rich_desktop",
                                key="ton_amount", value="2.25"))
        self.host.close()
        self.host = Host(self.root / "state")
        self.assertEqual(self.host.snapshot()["previews"]["ton"], "2.25")

    def test_crash_marker_disables_engine(self):
        self.enable()
        self.host.close()
        (self.root / "state/running").write_text("running")
        self.host = Host(self.root / "state")
        self.assertFalse(self.host.snapshot()["engine"])
        self.assertEqual(self.host.active, {})
        self.assertIn("unexpectedly", self.host.warning)

    def test_changed_source_is_not_executed(self):
        self.enable()
        self.host.close()
        path = self.host.path("feel_rich_desktop")
        path.write_bytes(path.read_bytes() + b'\nraise RuntimeError("changed")\n')
        self.host = Host(self.root / "state")
        self.assertEqual(self.host.active, {})
        self.assertFalse(self.host.snapshot()["plugins"][0]["compatible"])

    def test_pin_and_remove_preserve_original(self):
        self.enable()
        before = EXAMPLE.read_bytes()
        self.host.dispatch(dict(op="pin", plugin="feel_rich_desktop", value=True))
        self.assertTrue(self.host.snapshot()["plugins"][0]["pinned"])
        self.host.dispatch(dict(op="remove", plugin="feel_rich_desktop"))
        self.assertEqual(self.host.snapshot()["plugins"], [])
        self.assertEqual(self.host.snapshot()["previews"], {})
        self.assertEqual(EXAMPLE.read_bytes(), before)

    def test_corrupt_state_fails_closed(self):
        self.host.close()
        (self.root / "state/state.json").write_text('{"engine": true, "plugins": []}')
        self.host = Host(self.root / "state")
        self.assertFalse(self.host.snapshot()["engine"])
        self.assertIn("not loaded", self.host.warning)

    def test_load_failure_keeps_other_plugins_running(self):
        self.enable()
        path = self.make_plugin('__id__="broken"\n__name__="Broken"\n__platform__="desktop"\n'
                                '__desktop_api__=1\nraise RuntimeError("load failed")')
        self.install(path)
        with self.assertRaisesRegex(RuntimeError, "load failed"):
            self.host.dispatch(dict(op="enable", plugin="broken", value=True))
        self.assertEqual(self.host.snapshot()["previews"]["stars"], "1000")

    def test_switch_selector_and_unload_callback(self):
        path = self.make_plugin('''from base_plugin import BasePlugin
from ui.settings import Switch, Selector
__id__="controls"
__name__="Controls"
__platform__="desktop"
__desktop_api__=1
class Plugin(BasePlugin):
    def create_settings(self):
        return [Switch("switch", "Switch", True), Selector("choice", "Choice", 0, ["a", "b"])]
    def on_plugin_unload(self):
        self.set_setting("unloaded", True)
''')
        self.install(path)
        self.host.dispatch(dict(op="engine", value=True))
        self.host.dispatch(dict(op="enable", plugin="controls", value=True))
        self.host.dispatch(dict(op="set_setting", plugin="controls", key="switch", value=False))
        self.host.dispatch(dict(op="set_setting", plugin="controls", key="choice", value=1))
        with self.assertRaises(ValueError):
            self.host.dispatch(dict(op="set_setting", plugin="controls", key="choice", value=9))
        self.host.dispatch(dict(op="enable", plugin="controls", value=False))
        settings = self.host.state["plugins"]["controls"]["settings"]
        self.assertEqual(settings, {"switch": False, "choice": 1, "unloaded": True})

    def test_protocol_subprocess(self):
        requests = [dict(op="list"), dict(op="install", path=str(EXAMPLE)),
                    dict(op="engine", value=True),
                    dict(op="enable", plugin="feel_rich_desktop", value=True),
                    dict(op="shutdown")]
        process = subprocess.run(
            [sys.executable, "-u", "-B", str(RUNTIME / "host.py"), "--root", str(self.root / "rpc")],
            input="\n".join(json.dumps(dict(id=i, **request)) for i, request in enumerate(requests)) + "\n",
            text=True, capture_output=True, timeout=15)
        self.assertEqual(process.returncode, 0, process.stderr)
        results = [json.loads(line) for line in process.stdout.splitlines()]
        self.assertEqual(len(results), 5)
        self.assertTrue(all(result["ok"] for result in results))
        self.assertEqual(results[3]["snapshot"]["previews"]["stars"], "1000")
        self.assertEqual(results[4]["snapshot"]["previews"], {})

    def test_malformed_protocol_recovers(self):
        process = subprocess.run(
            [sys.executable, "-B", str(RUNTIME / "host.py"), "--root", str(self.root / "rpc")],
            input='[]\nnot json\n{"op":"shutdown","id":3}\n',
            text=True, capture_output=True, timeout=15)
        self.assertEqual(process.returncode, 0, process.stderr)
        results = [json.loads(line) for line in process.stdout.splitlines()]
        self.assertEqual([result["ok"] for result in results], [False, False, True])

    def test_plugin_system_exit_retains_recovery_marker(self):
        path = self.make_plugin('''from base_plugin import BasePlugin
from ui.settings import Input
__id__="exit_plugin"
__name__="Exit plugin"
__platform__="desktop"
__desktop_api__=1
class Plugin(BasePlugin):
    def create_settings(self):
        raise SystemExit(7)
''')
        root = self.root / "fatal"
        requests = [dict(op="install", path=str(path)), dict(op="engine", value=True),
                    dict(op="enable", plugin="exit_plugin", value=True),
                    dict(op="settings", plugin="exit_plugin")]
        process = subprocess.run(
            [sys.executable, "-B", str(RUNTIME / "host.py"), "--root", str(root)],
            input="\n".join(json.dumps(dict(id=i, **request)) for i, request in enumerate(requests)) + "\n",
            text=True, capture_output=True, timeout=15)
        self.assertEqual(process.returncode, 7)
        self.assertTrue((root / "running").exists())
        recovery = Host(root)
        self.addCleanup(recovery.close)
        self.assertFalse(recovery.snapshot()["engine"])
        self.assertEqual(recovery.active, {})


if __name__ == "__main__":
    unittest.main()
