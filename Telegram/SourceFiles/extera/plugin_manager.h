#pragma once

#include "core/credits_amount.h"
#include "rpl/event_stream.h"
#include "rpl/variable.h"

#include <QJsonObject>
#include <QMap>
#include <QObject>
#include <QProcess>
#include <QTimer>

namespace Extera {

class PluginManager final : public QObject {
public:
	static PluginManager &Instance();
	void start();
	void request(QJsonObject command, Fn<void(QJsonObject)> done = nullptr);
	[[nodiscard]] QJsonObject snapshot() const;
	[[nodiscard]] QString error() const;
	[[nodiscard]] QString directory() const;
	[[nodiscard]] bool ready() const;
	[[nodiscard]] rpl::producer<> changes() const;
	[[nodiscard]] rpl::producer<QString> previewValue(bool ton) const;

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

};

[[nodiscard]] rpl::producer<CreditsAmount> DisplayBalanceValue(
	rpl::producer<CreditsAmount> actual,
	bool ton);

}
