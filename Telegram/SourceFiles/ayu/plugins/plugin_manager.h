#pragma once

#include <QJsonObject>
#include <QString>
#include <QStringList>
#include <QVariant>
#include <QVariantMap>

#include <memory>

namespace Ayu::Plugins {

class PythonRuntime;

class PluginManager final {
public:
	struct LoadResult {
		bool ok = false;
		QString error;
		QVariantMap metadata;
	};

	static PluginManager &instance();

	bool initialize(const QString &runtimeRoot, const QString &pluginsRoot);
	void shutdown();

	[[nodiscard]] bool isInitialized() const;
	[[nodiscard]] QString pluginsRoot() const;
	[[nodiscard]] QStringList loadedPluginIds() const;

	LoadResult loadPlugin(const QString &path);
	bool unloadPlugin(const QString &pluginId, QString *error = nullptr);
	void loadAll();

	[[nodiscard]] QVariant getSetting(
		const QString &pluginId,
		const QString &key,
		const QVariant &fallback = {}) const;
	bool setSetting(
		const QString &pluginId,
		const QString &key,
		const QVariant &value,
		QString *error = nullptr);

	void log(const QString &pluginId, const QString &message) const;

private:
	PluginManager();
	~PluginManager();

	PluginManager(const PluginManager &) = delete;
	PluginManager &operator=(const PluginManager &) = delete;

	bool loadSettings();
	bool saveSettings(QString *error = nullptr) const;

	QString _pluginsRoot;
	QString _settingsPath;
	QJsonObject _settings;
	std::unique_ptr<PythonRuntime> _runtime;
	bool _initialized = false;
};

} // namespace Ayu::Plugins
