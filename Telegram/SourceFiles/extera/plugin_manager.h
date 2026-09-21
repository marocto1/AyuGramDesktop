#pragma once

#include "core/credits_amount.h"
#include "rpl/event_stream.h"
#include "rpl/variable.h"

#include <QJsonObject>
#include <QJsonValue>
#include <QMap>
#include <QObject>
#include <QProcess>
#include <QTimer>

namespace Extera {

class PluginManager final : public QObject {
public:
	static PluginManager &Instance();
	void start();
	void restart();
	void inspectPluginFile(QString path, Fn<void(QJsonObject)> done);
	void installPluginFile(QString path, Fn<void(QJsonObject)> done);
	void executeHook(QString kind, QString name, int account, QJsonValue value,
		Fn<void(QJsonObject)> done, QJsonValue error = QJsonValue());
	[[nodiscard]] QJsonObject executeHookBlocking(
		QString kind,
		QString name,
		int account,
		QJsonValue value,
		int timeoutMs = 500,
		QJsonValue error = QJsonValue());
	void request(QJsonObject command, Fn<void(QJsonObject)> done = nullptr);
	[[nodiscard]] QJsonObject snapshot() const;
	[[nodiscard]] QString error() const;
	[[nodiscard]] QString directory() const;
	[[nodiscard]] bool ready() const;
	[[nodiscard]] rpl::producer<> changes() const;
	[[nodiscard]] rpl::producer<QString> previewValue(bool ton) const;
	[[nodiscard]] bool unlimitedPins() const;
	[[nodiscard]] rpl::producer<bool> unlimitedPinsValue() const;
	[[nodiscard]] bool noForwardLimit() const;
	[[nodiscard]] rpl::producer<bool> noForwardLimitValue() const;
	[[nodiscard]] bool hasSendMessageHooks() const;

private:
	explicit PluginManager(QObject *parent);
	void receive();
	void fail(QString error);
	void shutdown();
	void applySnapshot(QJsonObject snapshot);

	QProcess _process;
	QTimer _watchdog;
	QByteArray _buffer;
	QJsonObject _snapshot;
	QString _error;
	QMap<int, Fn<void(QJsonObject)>> _pending;
	int _sequence = 0;
	bool _ready = false;
	bool _stopping = false;
	rpl::event_stream<> _changes;
	rpl::variable<QString> _stars;
	rpl::variable<QString> _ton;
	rpl::variable<bool> _unlimitedPins = false;
	rpl::variable<bool> _noForwardLimit = false;
	int _sendMessageHooks = 0;

};

[[nodiscard]] rpl::producer<CreditsAmount> DisplayBalanceValue(
	rpl::producer<CreditsAmount> actual,
	bool ton);

}
