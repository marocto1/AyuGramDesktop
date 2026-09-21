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
from base_plugin import BasePlugin, HookResult, HookStrategy
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

    def test_simple_java_import_is_bridged_without_install_execution(self):
        path = self.make_plugin('__id__="android_plugin"\n__name__="Android"\n'
                                'from java.lang import Boolean\nraise RuntimeError("executed")')
        self.install(path)
        meta = self.host.snapshot()["plugins"][0]
        self.assertTrue(meta["compatible"])
        self.assertEqual(meta["compatibility"], "bridged")
        self.assertFalse(meta["enabled"])

    def test_official_metadata_does_not_require_desktop_marker(self):
        meta = inspect_source(b'__id__="legacy"\n__name__="Legacy"\n__sdk_version__=">=1.4.4.3"')
        self.assertTrue(meta["compatible"])
        self.assertEqual(meta["sdk_version"], ">=1.4.4.3")

    def test_unlimited_pins_uses_native_desktop_adapter(self):
        path = self.make_plugin(
            '__id__="unlimited_pins"\n'
            '__name__="Unlimited Pins"\n'
            '__author__="@mihailkotovski & @mishabotov"\n'
            'from java.lang import Integer\n'
            'from org.telegram.messenger import MessagesController\n'
            'raise RuntimeError("android source must not execute on desktop")\n'
        )
        meta = inspect_source(path.read_bytes())
        self.assertTrue(meta["compatible"])
        self.assertEqual(meta["native_adapter"], "unlimited_pins")
        self.install(path)
        self.host.dispatch(dict(op="engine", value=True))
        result = self.host.dispatch(dict(op="enable", plugin="unlimited_pins", value=True))
        self.assertTrue(result["snapshot"]["native"]["unlimited_pins"])
        self.assertTrue(result["snapshot"]["plugins"][0]["active"])

    def test_inspect_does_not_install(self):
        path = self.make_plugin(
            '__id__="inspectable"\n'
            '__name__="Inspectable"\n'
            '__author__="Tester"\n'
        )
        result = self.host.dispatch(dict(op="inspect", path=str(path)))
        self.assertEqual(result["plugin"]["name"], "Inspectable")
        self.assertFalse((self.root / "plugins" / "inspectable.plugin").exists())
        self.assertEqual(result["snapshot"]["plugins"], [])

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


    def test_hook_runtime_priority_modify_and_final(self):
        first = self.make_plugin('''from base_plugin import BasePlugin, HookResult, HookStrategy
__id__="hook_first"
__name__="Hook First"
class Plugin(BasePlugin):
    def on_plugin_load(self):
        self.add_hook("messages.sendMessage", priority=20)
    def pre_request_hook(self, request_name, account, request):
        request["text"] += " first"
        return HookResult(HookStrategy.MODIFY, request=request)
''')
        self.install(first)
        second = self.root / "second.plugin"
        second.write_text('''from base_plugin import BasePlugin, HookResult, HookStrategy
__id__="hook_second"
__name__="Hook Second"
class Plugin(BasePlugin):
    def on_plugin_load(self):
        self.add_hook("messages.sendMessage", priority=10)
    def pre_request_hook(self, request_name, account, request):
        request["text"] += " second"
        return HookResult(HookStrategy.MODIFY_FINAL, request=request)
''', encoding="utf-8")
        self.install(second)
        self.host.dispatch(dict(op="engine", value=True))
        self.host.dispatch(dict(op="enable", plugin="hook_first", value=True))
        self.host.dispatch(dict(op="enable", plugin="hook_second", value=True))
        result = self.host.dispatch(dict(
            op="hook_pre_request",
            name="messages.sendMessage",
            account=0,
            value={"text": "hello"},
        ))["hook"]
        self.assertEqual(result["value"]["text"], "hello first second")
        self.assertTrue(result["final"])
        self.assertFalse(result["cancelled"])
        self.assertEqual(result["executed"], ["hook_first", "hook_second"])

    def test_hook_runtime_cancel_and_substring(self):
        path = self.make_plugin('''from base_plugin import BasePlugin, HookResult, HookStrategy
__id__="hook_cancel"
__name__="Hook Cancel"
class Plugin(BasePlugin):
    def on_plugin_load(self):
        self.add_hook("updateNew", match_substring=True, priority=50)
    def on_update_hook(self, update_name, account, update):
        return HookResult(HookStrategy.CANCEL)
''')
        self.install(path)
        self.host.dispatch(dict(op="engine", value=True))
        self.host.dispatch(dict(op="enable", plugin="hook_cancel", value=True))
        result = self.host.dispatch(dict(
            op="hook_update",
            name="updateNewMessage",
            account=0,
            value={"id": 123},
        ))["hook"]
        self.assertTrue(result["cancelled"])
        self.assertEqual(result["value"], {"id": 123})

    def test_send_message_hook_runtime(self):
        path = self.make_plugin('''from base_plugin import BasePlugin, HookResult, HookStrategy
__id__="send_hook"
__name__="Send Hook"
class Plugin(BasePlugin):
    def on_plugin_load(self):
        self.add_on_send_message_hook(priority=5)
    def on_send_message_hook(self, account, params):
        params["message"] = params["message"].upper()
        return HookResult(HookStrategy.MODIFY, params=params)
''')
        self.install(path)
        self.host.dispatch(dict(op="engine", value=True))
        self.host.dispatch(dict(op="enable", plugin="send_hook", value=True))
        result = self.host.dispatch(dict(
            op="hook_send_message",
            account=1,
            value={"peer_id": 42, "message": "hello"},
        ))["hook"]
        self.assertEqual(result["value"]["message"], "HELLO")
        self.assertEqual(result["executed"], ["send_hook"])

    def test_no_forward_limit_semantic_adapter(self):
        path = self.make_plugin(
            '__id__="zwyNoForwardLimit"\n__name__="NoForwardLimit"\n'
            'from java.lang import Integer\nfrom org.telegram.tgnet import TLRPC\n'
            'TOKEN="TL_messages_forwardMessages"\nHOOK="addToSelectedMessages"\nDELETE="deleteMessages"\n'
            'raise RuntimeError("android source must not execute")\n')
        meta = inspect_source(path.read_bytes())
        self.assertTrue(meta["compatible"])
        self.assertEqual(meta["compatibility"], "adapter")
        self.assertEqual(meta["native_adapter"], "no_forward_limit")
        self.install(path)
        self.host.dispatch(dict(op="engine", value=True))
        result = self.host.dispatch(dict(op="enable", plugin="zwyNoForwardLimit", value=True))
        self.assertTrue(result["snapshot"]["native"]["no_forward_limit"])

    def test_java_and_tgnet_imports_use_bridge(self):
        path = self.make_plugin('''from base_plugin import BasePlugin
from java.lang import Boolean, Integer
from java.util import ArrayList
from org.telegram.tgnet import TLObject, TLRPC
from org.telegram.messenger import LocaleController, UserConfig
__id__="bridge_imports"
__name__="Bridge imports"
class Plugin(BasePlugin):
    def on_plugin_load(self):
        values=ArrayList(); values.add(Integer(7))
        self.set_setting("ok", bool(Boolean(True)) and values.size()==1)
        self.set_setting("lang", LocaleController.getInstance().getCurrentLocale().getLanguage())
''')
        self.assertEqual(inspect_source(path.read_bytes())["compatibility"], "bridged")
        self.install(path)
        self.host.dispatch(dict(op="engine", value=True))
        self.host.dispatch(dict(op="enable", plugin="bridge_imports", value=True))
        self.assertTrue(self.host.state["plugins"]["bridge_imports"]["settings"]["ok"])

    def test_android_ui_method_hook_only_stays_unsupported(self):
        meta = inspect_source(b'__id__="ui_only"\n__name__="UI only"\nfrom android.widget import FrameLayout\nfrom org.telegram.ui import ChatActivity\ndef hook_method(x): pass\n')
        self.assertFalse(meta["compatible"])
        self.assertEqual(meta["compatibility"], "unsupported")

    def test_hook_params_support_attribute_access(self):
        path = self.make_plugin('''from base_plugin import BasePlugin, HookResult, HookStrategy
__id__="attr_hook"
__name__="Attr Hook"
class Plugin(BasePlugin):
    def on_plugin_load(self): self.add_on_send_message_hook()
    def on_send_message_hook(self, account, params):
        params.message=params.message.upper()
        return HookResult(strategy=HookStrategy.MODIFY, params=params)
''')
        self.install(path)
        self.host.dispatch(dict(op="engine", value=True))
        self.host.dispatch(dict(op="enable", plugin="attr_hook", value=True))
        result=self.host.dispatch(dict(op="hook_send_message", account=0, value={"message":"hello","peer":1}))
        self.assertEqual(result["hook"]["value"]["message"], "HELLO")

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
