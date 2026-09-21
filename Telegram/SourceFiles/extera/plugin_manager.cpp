#include "extera/plugin_manager.h"

#include "storage/localstorage.h"

#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QEventLoop>
#include <QJsonDocument>
#include <QRegularExpression>

namespace Extera {
namespace {

constexpr auto kResponseTimeout = 10000;
constexpr auto kMaxMessage = 2 * 1024 * 1024;

}

PluginManager &PluginManager::Instance() {
	static const auto result = new PluginManager(QCoreApplication::instance());
	result->start();
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
		const auto data = _process.readAllStandardError();
		if (data.isEmpty()) {
			return;
		}
		QDir().mkpath(directory());
		QFile file(QDir(directory()).absoluteFilePath(u"plugin-host.log"_q));
		if (file.open(QIODevice::WriteOnly | QIODevice::Append)) {
			file.write(data);
		}
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
		_ready = false;
		_error = u"Plugin runtime is missing. Run ExteraGram from the full portable folder with python/ and extera_runtime/ next to ExteraGram.exe, or set EXTERAGRAM_PYTHON to an absolute Python 3.11+ path."_q;
		_changes.fire({});
		return;
	}
	QDir().mkpath(directory());
	_error.clear();
	_buffer.clear();
	_stopping = false;
	_ready = false;
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
	if (!_process.waitForStarted(5000)) {
		fail(u"Could not start the Python plugin host: %1"_q.arg(_process.errorString()));
		return;
	}
	_ready = true;
	request({ { u"op"_q, u"list"_q } }, [=](QJsonObject result) {
		if (result.value(u"ok"_q).toBool()) {
			request({ { u"op"_q, u"app_event"_q }, { u"value"_q, u"start"_q } });
		}
	});
}

void PluginManager::restart() {
	shutdown();
	_stopping = false;
	start();
}

void PluginManager::inspectPluginFile(
		QString path,
		Fn<void(QJsonObject)> done) {
	start();
	request({
		{ u"op"_q, u"inspect"_q },
		{ u"path"_q, std::move(path) },
	}, std::move(done));
}

void PluginManager::installPluginFile(
		QString path,
		Fn<void(QJsonObject)> done) {
	start();
	request({
		{ u"op"_q, u"install"_q },
		{ u"path"_q, std::move(path) },
	}, std::move(done));
}

void PluginManager::executeHook(
		QString kind,
		QString name,
		int account,
		QJsonValue value,
		Fn<void(QJsonObject)> done,
		QJsonValue error) {
	start();
	auto command = QJsonObject{
		{ u"op"_q, u"hook_"_q + std::move(kind) },
		{ u"name"_q, std::move(name) },
		{ u"account"_q, account },
		{ u"value"_q, std::move(value) },
	};
	if (!error.isUndefined() && !error.isNull()) {
		command.insert(u"error"_q, std::move(error));
	}
	request(std::move(command), std::move(done));
}

QJsonObject PluginManager::executeHookBlocking(
		QString kind,
		QString name,
		int account,
		QJsonValue value,
		int timeoutMs,
		QJsonValue error) {
	if (!_ready) {
		return {};
	}
	struct State {
		QJsonObject result;
		bool done = false;
		QEventLoop *loop = nullptr;
	};
	const auto state = std::make_shared<State>();
	auto loop = QEventLoop();
	state->loop = &loop;
	executeHook(
		std::move(kind),
		std::move(name),
		account,
		std::move(value),
		[state](QJsonObject result) {
			state->result = std::move(result);
			state->done = true;
			if (state->loop) {
				state->loop->quit();
			}
		},
		std::move(error));
	if (!state->done) {
		QTimer::singleShot(std::max(1, timeoutMs), &loop, &QEventLoop::quit);
		loop.exec(QEventLoop::ExcludeUserInputEvents);
	}
	state->loop = nullptr;
	return state->done ? state->result : QJsonObject();
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
	const auto native = _snapshot.value(u"native"_q).toObject();
	const auto hooks = _snapshot.value(u"hooks"_q).toObject();
	_stars = previews.value(u"stars"_q).toString();
	_ton = previews.value(u"ton"_q).toString();
	_unlimitedPins = native.value(u"unlimited_pins"_q).toBool();
	_noForwardLimit = native.value(u"no_forward_limit"_q).toBool();
	_sendMessageHooks = hooks.value(u"send_message"_q).toInt();
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
	_unlimitedPins = false;
	_noForwardLimit = false;
	_sendMessageHooks = 0;
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

bool PluginManager::unlimitedPins() const {
	return _unlimitedPins.current();
}

rpl::producer<bool> PluginManager::unlimitedPinsValue() const {
	return _unlimitedPins.value();
}
bool PluginManager::noForwardLimit() const {
	return _noForwardLimit.current();
}
rpl::producer<bool> PluginManager::noForwardLimitValue() const {
	return _noForwardLimit.value();
}

bool PluginManager::hasSendMessageHooks() const {
	return _sendMessageHooks > 0;
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
