#pragma once

#include <QString>
#include <QStringList>
#include <QVariantMap>

#include <memory>

namespace Ayu::Plugins {

class PluginManager;

class PythonRuntime final {
public:
	struct LoadResult {
		bool ok = false;
		QString error;
		QVariantMap metadata;
	};

	explicit PythonRuntime(PluginManager *manager);
	~PythonRuntime();

	bool initialize(const QString &runtimeRoot, QString *error = nullptr);
	void shutdown();

	[[nodiscard]] bool isInitialized() const;
	LoadResult loadPlugin(const QString &path);
	bool unloadPlugin(const QString &pluginId, QString *error = nullptr);
	[[nodiscard]] QStringList loadedPluginIds(QString *error = nullptr) const;

private:
	struct Private;
	std::unique_ptr<Private> _private;
};

} // namespace Ayu::Plugins
