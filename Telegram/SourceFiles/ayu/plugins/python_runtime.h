#pragma once

#include <QString>
#include <QStringList>
#include <QVariantMap>

#include <memory>
#include <optional>

namespace Ayu::Plugins {

class PluginManager;

class PythonRuntime final {
public:
	struct LoadResult {
		bool ok = false;
		QString error;
		QVariantMap metadata;
	};

	struct SendMessageResult {
		bool cancelled = false;
		QString message;
	};

	explicit PythonRuntime(PluginManager *manager);
	~PythonRuntime();

	bool initialize(const QString &runtimeRoot, QString *error = nullptr);
	void shutdown();

	[[nodiscard]] bool isInitialized() const;
	LoadResult loadPlugin(const QString &path);
	bool unloadPlugin(const QString &pluginId, QString *error = nullptr);
	[[nodiscard]] QStringList loadedPluginIds(QString *error = nullptr) const;
	[[nodiscard]] std::optional<SendMessageResult> dispatchTextMessage(
		qint64 account,
		const QString &message,
		QString *error = nullptr) const;

private:
	struct Private;
	std::unique_ptr<Private> _private;
};

} // namespace Ayu::Plugins
