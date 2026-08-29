#include "ayu/plugins/plugin_manager.h"

#include "ayu/plugins/python_runtime.h"

#include <QDebug>
#include <QDir>
#include <QFile>
#include <QJsonDocument>
#include <QSaveFile>

namespace Ayu::Plugins {

PluginManager &PluginManager::instance() {
	static auto result = PluginManager();
	return result;
}

PluginManager::PluginManager() = default;

PluginManager::~PluginManager() {
	shutdown();
}

bool PluginManager::initialize(
		const QString &runtimeRoot,
		const QString &pluginsRoot) {
	if (_initialized) {
		return true;
	}

	_pluginsRoot = QDir(pluginsRoot).absolutePath();
	if (!QDir().mkpath(_pluginsRoot)) {
		qWarning().noquote()
			<< "[AyuPlugins] Could not create plugin directory:"
			<< _pluginsRoot;
		return false;
	}

	_settingsPath = QDir(_pluginsRoot).filePath(QStringLiteral("settings.json"));
	if (!loadSettings()) {
		qWarning().noquote()
			<< "[AyuPlugins] settings.json is invalid; starting with empty settings";
		_settings = QJsonObject();
	}

	_runtime = std::make_unique<PythonRuntime>(this);
	auto error = QString();
	if (!_runtime->initialize(runtimeRoot, &error)) {
		qWarning().noquote()
			<< "[AyuPlugins] Python runtime initialization failed:"
			<< error;
		_runtime.reset();
		return false;
	}

	_initialized = true;
	loadAll();
	return true;
}

void PluginManager::shutdown() {
	if (_runtime) {
		_runtime->shutdown();
		_runtime.reset();
	}
	_initialized = false;
}

bool PluginManager::isInitialized() const {
	return _initialized;
}

QString PluginManager::pluginsRoot() const {
	return _pluginsRoot;
}

QStringList PluginManager::loadedPluginIds() const {
	if (!_runtime) {
		return {};
	}
	auto error = QString();
	auto result = _runtime->loadedPluginIds(&error);
	if (!error.isEmpty()) {
		qWarning().noquote()
			<< "[AyuPlugins] Could not query loaded plugins:"
			<< error;
	}
	return result;
}

PluginManager::LoadResult PluginManager::loadPlugin(const QString &path) {
	auto result = LoadResult();
	if (!_runtime) {
		result.error = QStringLiteral("Plugin runtime is not initialized");
		return result;
	}

	const auto runtimeResult = _runtime->loadPlugin(path);
	result.ok = runtimeResult.ok;
	result.error = runtimeResult.error;
	result.metadata = runtimeResult.metadata;
	if (result.ok) {
		qInfo().noquote()
			<< "[AyuPlugins] Loaded"
			<< result.metadata.value(QStringLiteral("id")).toString()
			<< "from" << path;
	} else {
		qWarning().noquote()
			<< "[AyuPlugins] Failed to load" << path << ":" << result.error;
	}
	return result;
}

bool PluginManager::unloadPlugin(const QString &pluginId, QString *error) {
	if (!_runtime) {
		if (error) {
			*error = QStringLiteral("Plugin runtime is not initialized");
		}
		return false;
	}
	return _runtime->unloadPlugin(pluginId, error);
}

void PluginManager::loadAll() {
	if (!_runtime) {
		return;
	}

	const auto directory = QDir(_pluginsRoot);
	const auto files = directory.entryInfoList(
		{ QStringLiteral("*.plugin") },
		QDir::Files | QDir::Readable,
		QDir::Name | QDir::IgnoreCase);
	for (const auto &file : files) {
		loadPlugin(file.absoluteFilePath());
	}
}

QVariant PluginManager::getSetting(
		const QString &pluginId,
		const QString &key,
		const QVariant &fallback) const {
	const auto plugin = _settings.value(pluginId);
	if (!plugin.isObject()) {
		return fallback;
	}
	const auto object = plugin.toObject();
	const auto value = object.value(key);
	return value.isUndefined() ? fallback : value.toVariant();
}

bool PluginManager::setSetting(
		const QString &pluginId,
		const QString &key,
		const QVariant &value,
		QString *error) {
	if (pluginId.isEmpty() || key.isEmpty()) {
		if (error) {
			*error = QStringLiteral("plugin id and setting key must not be empty");
		}
		return false;
	}

	auto object = _settings.value(pluginId).toObject();
	object.insert(key, QJsonValue::fromVariant(value));
	_settings.insert(pluginId, object);
	return saveSettings(error);
}

void PluginManager::log(
		const QString &pluginId,
		const QString &message) const {
	qInfo().noquote()
		<< QStringLiteral("[AyuPlugin:%1]").arg(pluginId)
		<< message;
}

bool PluginManager::loadSettings() {
	_settings = QJsonObject();
	auto file = QFile(_settingsPath);
	if (!file.exists()) {
		return true;
	}
	if (!file.open(QIODevice::ReadOnly)) {
		return false;
	}

	auto parseError = QJsonParseError();
	const auto document = QJsonDocument::fromJson(file.readAll(), &parseError);
	if (parseError.error != QJsonParseError::NoError || !document.isObject()) {
		return false;
	}
	_settings = document.object();
	return true;
}

bool PluginManager::saveSettings(QString *error) const {
	auto file = QSaveFile(_settingsPath);
	if (!file.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
		if (error) {
			*error = file.errorString();
		}
		return false;
	}

	const auto data = QJsonDocument(_settings).toJson(QJsonDocument::Indented);
	if (file.write(data) != data.size()) {
		if (error) {
			*error = file.errorString();
		}
		return false;
	}
	if (!file.commit()) {
		if (error) {
			*error = file.errorString();
		}
		return false;
	}
	return true;
}

} // namespace Ayu::Plugins
