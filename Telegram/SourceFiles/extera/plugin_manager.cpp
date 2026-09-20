#include "extera/plugin_manager.h"

#include "storage/localstorage.h"

#include <QCoreApplication>
#include <QDir>
#include <QFileInfo>
#include <QJsonDocument>
#include <QRegularExpression>

namespace Extera {
namespace {

constexpr auto kResponseTimeout = 10000;
constexpr auto kMaxMessage = 2 * 1024 * 1024;

}

PluginManager &PluginManager::Instance() {
	static const auto result = new PluginManager(QCoreApplication::instance());
	return *result;
}

PluginManager::PluginManager(QObject *parent) : QObject(parent) {
	_watchdog.setSingleShot(true);
	QObject::connect(&_watchdog, &QTimer::timeout, this, [=] {
		fail(u"Plugin timed out. Engine stopped; restart it from ExteraGram settings."_q);
	});
	QObject::connect(&_process, &QProcess::readyReadStandardOutput,
		this, [=] { receive(); });
	QObject::connect(&_process, &QProcess::readyReadStandardError, this, [=] {
		_process.readAllStandardError();
	});
	QObject::connect(&_process, &QProcess::errorOccurred,
		this, [=](QProcess::ProcessError) {
		if (!_stopping) {
			fail(_process.errorString());
		}
	});
	QObject::connect(&_process,
		qOverload<int, QProcess::ExitStatus>(&QProcess::finished),
		this, [=](int code, QProcess::ExitStatus) {
		if (!_stopping) {
			fail(u"Plugin host exited (%1). Engine stopped."_q.arg(code));
		}
	});
	QObject::connect(QCoreApplication::instance(), &QCoreApplication::aboutToQuit,
		this, [=] { shutdown(); });
}

void PluginManager::start() {
	if (_process.state() != QProcess::NotRunning) {
		return;
	}
	const auto app = QCoreApplication::applicationDirPath();
	auto python = qEnvironmentVariable("EXTERAGRAM_PYTHON");
	if (python.isEmpty()) {
#ifdef Q_OS_WIN
		python = app + u"/python/python.exe"_q;
#else
		python = app + u"/python/bin/python3"_q;
#endif
	}
	const auto script = app + u"/extera_runtime/host.py"_q;
	if (!QFileInfo(python).isAbsolute()
		|| !QFileInfo::exists(python)
		|| !QFileInfo::exists(script)) {
		_error = u"Plugin runtime is missing. Keep the python and extera_runtime folders next to the app, or set EXTERAGRAM_PYTHON to an absolute Python 3.11+ path."_q;
		_changes.fire({});
		return;
	}
	_error.clear();
	_buffer.clear();
	_stopping = false;
	_ready = true;
	_process.setWorkingDirectory(app + u"/extera_runtime"_q);
	_process.start(python, {
		u"-u"_q,
		u"-B"_q,
		u"-E"_q,
		u"-s"_q,
		script,
		u"--root"_q,
		directory(),
	});
	request({ { u"op"_q, u"list"_q } });
}

void PluginManager::request(QJsonObject command, Fn<void(QJsonObject)> done) {
	if (!_ready || _pending.size() >= 32) {
		if (done) {
			done({ { u"ok"_q, false }, { u"error"_q,
				_ready ? u"Plugin request queue is full."_q : _error } });
		}
		return;
	}
	const auto id = ++_sequence;
	command.insert(u"id"_q, id);
	_pending.insert(id, std::move(done));
	_process.write(QJsonDocument(command).toJson(QJsonDocument::Compact) + '\n');
	if (!_watchdog.isActive()) {
		_watchdog.start(kResponseTimeout);
	}
}

void PluginManager::receive() {
	if (_stopping) {
		_process.readAllStandardOutput();
		return;
	}
	_buffer += _process.readAllStandardOutput();
	while (true) {
		const auto newline = _buffer.indexOf('\n');
		if (newline < 0) {
			if (_buffer.size() > kMaxMessage) {
				fail(u"Plugin response exceeded the size limit."_q);
			}
			return;
		}
		if (newline > kMaxMessage) {
			fail(u"Plugin response exceeded the size limit."_q);
			return;
		}
		auto error = QJsonParseError();
		const auto doc = QJsonDocument::fromJson(_buffer.left(newline), &error);
		_buffer.remove(0, newline + 1);
		const auto result = doc.object();
		const auto id = result.value(u"id"_q).toInt();
		if (error.error != QJsonParseError::NoError || !_pending.contains(id)) {
			fail(u"Invalid plugin host response."_q);
			return;
		}
		if (result.contains(u"snapshot"_q)) {
			applySnapshot(result.value(u"snapshot"_q).toObject());
		}
		auto callback = _pending.take(id);
		if (_pending.empty()) {
			_watchdog.stop();
		} else {
			_watchdog.start(kResponseTimeout);
		}
		if (callback) {
			callback(result);
		}
	}
}

void PluginManager::applySnapshot(QJsonObject snapshot) {
	_snapshot = std::move(snapshot);
	const auto previews = _snapshot.value(u"previews"_q).toObject();
	_stars = previews.value(u"stars"_q).toString();
	_ton = previews.value(u"ton"_q).toString();
	_changes.fire({});
}

void PluginManager::fail(QString error) {
	_stopping = true;
	_ready = false;
	_error = std::move(error);
	_watchdog.stop();
	_process.kill();
	_stars = QString();
	_ton = QString();
	_snapshot.insert(u"engine"_q, false);
	_snapshot.insert(u"previews"_q, QJsonObject());
	const auto pending = std::exchange(_pending, {});
	for (const auto &callback : pending) {
		if (callback) {
			callback({ { u"ok"_q, false }, { u"error"_q, _error } });
		}
	}
	_changes.fire({});
}

void PluginManager::shutdown() {
	_stopping = true;
	_ready = false;
	_watchdog.stop();
	if (_process.state() != QProcess::NotRunning) {
		_process.write("{\"op\":\"shutdown\",\"id\":0}\n");
		_process.closeWriteChannel();
		if (!_process.waitForFinished(1000)) {
			_process.kill();
			_process.waitForFinished(1000);
		}
	}
}

QJsonObject PluginManager::snapshot() const {
	return _snapshot;
}

QString PluginManager::error() const {
	return _error;
}

QString PluginManager::directory() const {
	return QDir(cWorkingDir()).absoluteFilePath(u"tdata/extera"_q);
}

bool PluginManager::ready() const {
	return _ready;
}

rpl::producer<> PluginManager::changes() const {
	return _changes.events();
}

rpl::producer<QString> PluginManager::previewValue(bool ton) const {
	return ton ? _ton.value() : _stars.value();
}

rpl::producer<CreditsAmount> DisplayBalanceValue(
		rpl::producer<CreditsAmount> actual,
		bool ton) {
	return rpl::combine(std::move(actual),
		PluginManager::Instance().previewValue(ton)
	) | rpl::map([=](CreditsAmount amount, const QString &preview) {
		static const auto pattern = QRegularExpression(
			u"^([0-9]{1,11})(?:\\.([0-9]{1,9}))?$"_q);
		const auto match = pattern.match(preview);
		if (!match.hasMatch()) {
			return amount;
		}
		const auto whole = match.captured(1).toLongLong();
		const auto nano = match.captured(2).leftJustified(9, '0').toLongLong();
		if (whole > 10'000'000'000LL
			|| (whole == 10'000'000'000LL && nano)) {
			return amount;
		}
		return CreditsAmount(whole, nano,
			ton ? CreditsType::Ton : CreditsType::Stars);
	});
}

}
