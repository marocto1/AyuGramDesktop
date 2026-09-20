import copy
from decimal import Decimal, InvalidOperation


class BasePlugin:
    def __init__(self):
        self._settings = {}
        self._previews = {}
        self._logs = []
        self.id = ""

    def on_plugin_load(self):
        pass

    def on_plugin_unload(self):
        pass

    def create_settings(self):
        return []

    def get_setting(self, key, default=None):
        return copy.deepcopy(self._settings.get(key, default))

    def set_setting(self, key, value, reload_settings=False):
        if not isinstance(key, str) or len(key) > 128:
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
        self._logs.append(str(message)[:1000])
        del self._logs[:-20]

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
