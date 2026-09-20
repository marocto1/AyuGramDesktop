# ExteraGram Desktop plugins — API 1 (experimental)

This is an independent desktop extension of [AyuGram Desktop](https://github.com/AyuGram/AyuGramDesktop), not an official exteraGram release. Existing AyuGram features and attribution are retained.

## Использование

1. Распакуйте **весь** архив Actions, включая `python`, `extera_runtime` и `plugin_examples`, и запустите `AyuGram.exe`.
2. Откройте **Настройки → ExteraGram → Plugins**.
3. Включите систему плагинов, прочитав предупреждение.
4. Импортируйте `plugin_examples/feel_rich_desktop.plugin`. Импорт читает метаданные через AST, не выполняя код. Новый плагин всегда выключен.
5. Включите плагин и откройте его настройки. После изменения суммы нажмите **Save** рядом с полем.
6. В разделе Stars/TON заголовок баланса покажет локальное значение с подписью **Local preview only**. Серверный баланс, покупки, переводы, история операций и долларовый эквивалент остаются настоящими.

Поиск работает по имени, автору и ID. Закреплённые плагины выводятся первыми. Удаление очищает установленную копию и её настройки, но сохраняет исходный импортированный файл.

## Совместимость с Android

Формат `.plugin`, метаданные, `BasePlugin`, lifecycle и часть настроек похожи на [SDK exteraGram](https://plugins.exteragram.app/docs). **Это не полная совместимость с Android SDK.**

Исходный `feel_rich.plugin` использует `java.lang`, `StarsController`, `TL_stars`, reflection и Xposed. В C++/Qt нет этих Android-классов. Такой файл можно импортировать для просмотра информации, но включение блокируется с объяснением. Пример Desktop написан отдельно по описанию поведения; исходный сторонний файл не распространяется.

Поддерживаются:

- `__id__`, `__name__`, `__description__`, `__author__`, `__version__`, `__icon__` (метаданные; Android sticker icons не загружаются).
- Обязательная декларация `__platform__ = "desktop"`, `__desktop_api__ = 1`.
- `on_plugin_load`, `on_plugin_unload`, `create_settings`.
- `get_setting`, `set_setting`, `export_settings`, `import_settings`, `log`.
- `ui.settings.Header`, `Divider`, `Input`, `Switch`, `Selector`; callbacks `on_change`.
- Desktop-only `set_balance_preview(amount, currency="stars")` и `clear_balance_preview(currency="stars")`; валюта `stars` или `ton`, от 0 до 10¹⁰, максимум 9 десятичных знаков.

Пока отсутствуют Java/Xposed hooks, Telegram request/update hooks, отправка сообщений, Android UI, PIP, Elyx-пакеты, custom views и фоновые callback-события. Эффекты синхронизируются при ответах на команды хоста, не из фоновых потоков. Сторонние зависимости не устанавливаются автоматически. Если несколько плагинов задают одну валюту, побеждает последний установленный активный плагин; закрепление не меняет этот порядок. Настройки и preview общие для локальной установки, не раздельные по Telegram-аккаунтам.

## Минимальный плагин

```python
from base_plugin import BasePlugin
from ui.settings import Input

__id__ = "my_preview"
__name__ = "My preview"
__platform__ = "desktop"
__desktop_api__ = 1

class Plugin(BasePlugin):
    def on_plugin_load(self):
        self.set_balance_preview(self.get_setting("amount", "1000"))

    def create_settings(self):
        return [Input("amount", "Stars", "1000",
                      on_change=self.set_balance_preview)]
```

## Execution and storage

The Qt UI talks to a persistent Python subprocess over newline-delimited JSON on stdin/stdout. No listening socket is opened. Responses have request IDs, a 2 MiB limit and a 10-second response watchdog. Failure clears all visible preview overrides. A crash marker disables autoload after an unclean exit. Closing the app or disabling the engine invokes unload callbacks; a hung host is killed after a bounded wait.

**This is not a security sandbox.** Enabled Python plugins have the user's OS-level file and network access, including potential access to Telegram data. Import-time AST checks are a compatibility check, not a security audit. Run only reviewed, trusted plugins. No installed plugins are bundled or enabled automatically. Hash checks reject files modified outside the importer. They are not code signatures.

State lives under the client's working directory in `tdata/extera/state.json`, with source copies in `tdata/extera/plugins`. JSON writes use temporary files and atomic replacement. Settings are not encrypted. Avoid storing secrets in plugin settings.

Windows builds bundle CPython 3.13.12 with a pinned official archive SHA-256. The runtime requires Windows 8.1 or newer; this extension does not preserve AyuGram's Windows 7 plugin support. For a local developer build, set `EXTERAGRAM_PYTHON` to the absolute path of Python 3.11+ and keep `extera_runtime` next to the executable. The environment override selects an executable, not a shell command.

## GitHub Actions

Workflow: `.github/workflows/extera-windows.yml`. Push to `dev` or use **Actions → ExteraGram Windows → Run workflow**.

The matrix runs the Python tests on Windows and Linux with Python 3.11 and 3.13. The Windows job clones recursive submodules, prepares upstream Qt5/MSVC dependencies, builds **Debug x64**, packages Python and the example, verifies the bundled runtime protocol and uploads `ExteraGramDesktop-Windows-x64-Debug` with checksums. A first full dependency build can take hours; later runs use the dependency cache. Logs are uploaded even on failure. A green Python test job alone does not mean the desktop application compiled successfully.

Set repository secrets `TDESKTOP_API_ID` and `TDESKTOP_API_HASH` for your own Telegram application. With no secrets, the workflow uses upstream's explicit `TDESKTOP_API_TEST=ON`; this is a development build, not a public deployment build. No production credentials are embedded in this fork. Auto-update is disabled so an upstream update does not silently replace the plugin-enabled binary.

## Tests and rollback

```console
python -B -m unittest discover -s tests/extera -v
```

Turning off the engine removes all preview effects without deleting settings. Turning off one plugin unloads it. For source rollback use `git revert` on the implementation commit(s); keep existing user data. To revert just the feature files with hash checks, use `scripts/rollback-extera.ps1` and the manifest produced by `scripts/verify-extera.py`. The rollback script defaults to checking only; pass `-Apply` to restore the exact captured upstream files.

Manual acceptance after a successful C++ build: open the settings tab; import a desktop plugin; enable, edit, disable, restart and remove it; search and pin; import an Android plugin and confirm it stays incompatible; kill a test host and confirm previews disappear and startup recovery disables the engine; confirm actual payment calculations still use the original Credits API. These GUI checks require running the built client and are separate from the Python unit tests.
