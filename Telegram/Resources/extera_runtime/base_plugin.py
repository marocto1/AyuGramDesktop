import copy
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Callable, Optional
import uuid


class AppEvent(Enum):
    START = "start"
    STOP = "stop"
    PAUSE = "pause"
    RESUME = "resume"


class HookStrategy(Enum):
    DEFAULT = "default"
    CANCEL = "cancel"
    MODIFY = "modify"
    MODIFY_FINAL = "modify_final"


@dataclass
class HookResult:
    strategy: HookStrategy = HookStrategy.DEFAULT
    request: Any = None
    response: Any = None
    update: Any = None
    updates: Any = None
    params: Any = None


class MenuItemType(Enum):
    MESSAGE_CONTEXT_MENU = "message_context_menu"
    DRAWER_MENU = "drawer_menu"
    MAIN_MENU = "main_menu"
    CHAT_ACTION_MENU = "chat_action_menu"
    PROFILE_ACTION_MENU = "profile_action_menu"


@dataclass
class MenuItemData:
    menu_type: MenuItemType
    text: str
    on_click: Callable[[dict], None]
    item_id: Optional[str] = None
    icon: Optional[str] = None
    subtext: Optional[str] = None
    condition: Optional[str] = None
    priority: int = 0


class DesktopUnsupportedError(NotImplementedError):
    pass


class DesktopClient:
    def __init__(self, plugin, account=None):
        self.plugin = plugin
        self.account = account

    def _unsupported(self, feature):
        raise DesktopUnsupportedError(
            f"{feature} is not wired to Telegram Desktop yet. "
            "This plugin API is running in desktop compatibility mode."
        )

    def send_text(self, *args, **kwargs): self._unsupported("send_text")
    def send_photo(self, *args, **kwargs): self._unsupported("send_photo")
    def send_document(self, *args, **kwargs): self._unsupported("send_document")
    def send_video(self, *args, **kwargs): self._unsupported("send_video")
    def send_audio(self, *args, **kwargs): self._unsupported("send_audio")
    def send_request(self, *args, **kwargs): self._unsupported("send_request")


class BasePlugin:
    def __init__(self):
        self._settings = {}
        self._previews = {}
        self._logs = []
        self._hooks = []
        self._send_message_hook = None
        self._menu_items = {}
        self.id = ""

    def on_plugin_load(self): pass
    def on_plugin_unload(self): pass
    def on_app_event(self, event_type: AppEvent): pass
    def pre_request_hook(self, request_name, account, request): return HookResult()
    def post_request_hook(self, request_name, account, response, error): return HookResult()
    def on_update_hook(self, update_name, account, update): return HookResult()
    def on_updates_hook(self, container_name, account, updates): return HookResult()
    def on_send_message_hook(self, account, params): return HookResult()
    def create_settings(self): return []

    def get_setting(self, key, default=None):
        return copy.deepcopy(self._settings.get(key, default))

    def set_setting(self, key, value, reload_settings=False):
        if not isinstance(key, str) or not key or len(key) > 128:
            raise ValueError("Invalid setting key")
        self._settings[key] = copy.deepcopy(value)

    def export_settings(self):
        return copy.deepcopy(self._settings)

    def import_settings(self, settings, reload_settings=True):
        if not isinstance(settings, dict):
            raise ValueError("Settings must be an object")
        for key, value in settings.items():
            self.set_setting(key, value)

    def log(self, message):
        self._logs.append(str(message)[:2000])
        del self._logs[:-100]

    def add_hook(self, name, match_substring=False, priority=0):
        if not isinstance(name, str) or not name:
            raise ValueError("Hook name must be a non-empty string")
        priority = int(priority)
        item = {"name": name, "match_substring": bool(match_substring), "priority": priority}
        self._hooks.append(item)
        self._hooks.sort(key=lambda x: x["priority"], reverse=True)
        return item

    def remove_hook(self, handle):
        try:
            self._hooks.remove(handle)
            return True
        except ValueError:
            return False

    def add_on_send_message_hook(self, priority=0):
        self._send_message_hook = int(priority)
        return self._send_message_hook

    def remove_on_send_message_hook(self):
        existed = self._send_message_hook is not None
        self._send_message_hook = None
        return existed

    def add_menu_item(self, data: MenuItemData):
        if not isinstance(data, MenuItemData):
            raise TypeError("Expected MenuItemData")
        item_id = data.item_id or f"{self.id or 'plugin'}_{uuid.uuid4().hex[:12]}"
        self._menu_items[item_id] = data
        return item_id

    def remove_menu_item(self, item_id):
        return self._menu_items.pop(item_id, None) is not None

    def client(self, account=None):
        return DesktopClient(self, account)

    def set_balance_preview(self, amount, currency="stars"):
        if currency not in ("stars", "ton"):
            raise ValueError("Expected stars or ton")
        try:
            value = Decimal(str(amount))
            if not value.is_finite() or not 0 <= value <= 10**10:
                raise ValueError("Amount must be between 0 and 10000000000")
            if value != value.quantize(Decimal("0.000000001")):
                raise ValueError("At most nine decimal places are supported")
        except InvalidOperation as error:
            raise ValueError("Invalid amount") from error
        self._previews[currency] = format(value, "f")

    def clear_balance_preview(self, currency="stars"):
        self._previews.pop(currency, None)
