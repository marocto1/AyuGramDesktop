#include "ayu/plugins/python_runtime.h"

#include "ayu/plugins/plugin_manager.h"
#include "ayu/plugins/python_bridge.h"

#if defined(AYUGRAM_ENABLE_PYTHON_PLUGINS)
#include <Python.h>
#endif

#include <QFileInfo>
#include <QVariantList>

namespace Ayu::Plugins {

struct PythonRuntime::Private {
	explicit Private(PluginManager *owner) : manager(owner) {
	}

	PluginManager *manager = nullptr;
	bool initialized = false;
	bool ownsInterpreter = false;
#if defined(AYUGRAM_ENABLE_PYTHON_PLUGINS)
	PyObject *loaderModule = nullptr;
#endif
};

namespace {

#if defined(AYUGRAM_ENABLE_PYTHON_PLUGINS)

QString PythonError() {
	if (!PyErr_Occurred()) {
		return {};
	}

	PyObject *type = nullptr;
	PyObject *value = nullptr;
	PyObject *traceback = nullptr;
	PyErr_Fetch(&type, &value, &traceback);
	PyErr_NormalizeException(&type, &value, &traceback);

	auto result = QStringLiteral("Python error");
	if (value) {
		auto *text = PyObject_Str(value);
		if (text) {
			if (const auto utf8 = PyUnicode_AsUTF8(text)) {
				result = QString::fromUtf8(utf8);
			}
			Py_DECREF(text);
		}
	}

	Py_XDECREF(type);
	Py_XDECREF(value);
	Py_XDECREF(traceback);
	return result;
}

QString PyString(PyObject *value) {
	if (!value || !PyUnicode_Check(value)) {
		return {};
	}
	const auto utf8 = PyUnicode_AsUTF8(value);
	return utf8 ? QString::fromUtf8(utf8) : QString();
}

QVariant PyToVariant(PyObject *value) {
	if (!value || value == Py_None) {
		return {};
	}
	if (PyBool_Check(value)) {
		return QVariant(value == Py_True);
	}
	if (PyLong_Check(value)) {
		const auto number = PyLong_AsLongLong(value);
		if (!PyErr_Occurred()) {
			return QVariant::fromValue<qlonglong>(number);
		}
		PyErr_Clear();
	}
	if (PyFloat_Check(value)) {
		return QVariant(PyFloat_AsDouble(value));
	}
	if (PyUnicode_Check(value)) {
		return QVariant(PyString(value));
	}
	if (PyList_Check(value) || PyTuple_Check(value)) {
		auto result = QVariantList();
		const auto count = PySequence_Size(value);
		for (Py_ssize_t i = 0; i < count; ++i) {
			auto *item = PySequence_GetItem(value, i);
			result.push_back(PyToVariant(item));
			Py_XDECREF(item);
		}
		return result;
	}
	if (PyDict_Check(value)) {
		auto result = QVariantMap();
		PyObject *key = nullptr;
		PyObject *item = nullptr;
		Py_ssize_t pos = 0;
		while (PyDict_Next(value, &pos, &key, &item)) {
			if (PyUnicode_Check(key)) {
				result.insert(PyString(key), PyToVariant(item));
			}
		}
		return result;
	}
	return {};
}

bool PrependSysPath(const QString &path, QString *error) {
	auto *sysPath = PySys_GetObject("path");
	if (!sysPath || !PyList_Check(sysPath)) {
		if (error) {
			*error = QStringLiteral("Python sys.path is unavailable");
		}
		return false;
	}

	const auto utf8 = QFileInfo(path).absoluteFilePath().toUtf8();
	auto *entry = PyUnicode_FromStringAndSize(utf8.constData(), utf8.size());
	if (!entry) {
		if (error) {
			*error = PythonError();
		}
		return false;
	}
	const auto inserted = PyList_Insert(sysPath, 0, entry) == 0;
	Py_DECREF(entry);
	if (!inserted && error) {
		*error = PythonError();
	}
	return inserted;
}

PyObject *CallLoader(PyObject *loader, const char *name, PyObject *args) {
	auto *function = PyObject_GetAttrString(loader, name);
	if (!function) {
		return nullptr;
	}
	if (!PyCallable_Check(function)) {
		Py_DECREF(function);
		PyErr_Format(PyExc_TypeError, "loader.%s is not callable", name);
		return nullptr;
	}
	auto *result = PyObject_CallObject(function, args);
	Py_DECREF(function);
	return result;
}

#endif

} // namespace

PythonRuntime::PythonRuntime(PluginManager *manager)
: _private(std::make_unique<Private>(manager)) {
}

PythonRuntime::~PythonRuntime() {
	shutdown();
}

bool PythonRuntime::initialize(const QString &runtimeRoot, QString *error) {
	if (_private->initialized) {
		return true;
	}

#if !defined(AYUGRAM_ENABLE_PYTHON_PLUGINS)
	if (error) {
		*error = QStringLiteral(
			"AyuGram was built without AYUGRAM_ENABLE_PYTHON_PLUGINS");
	}
	return false;
#else
	if (Py_IsInitialized()) {
		if (error) {
			*error = QStringLiteral(
				"A Python interpreter is already initialized in this process");
		}
		return false;
	}

	setBridgePluginManager(_private->manager);
	if (!registerPythonBridgeModule()) {
		if (error) {
			*error = QStringLiteral("Could not register _ayugram_desktop module");
		}
		setBridgePluginManager(nullptr);
		return false;
	}

	PyConfig config;
	PyConfig_InitPythonConfig(&config);
	config.isolated = 1;
	config.use_environment = 0;
	config.user_site_directory = 0;
	config.site_import = 0;
	config.parse_argv = 0;
	config.install_signal_handlers = 0;
	config.write_bytecode = 0;

	const auto status = Py_InitializeFromConfig(&config);
	PyConfig_Clear(&config);
	if (PyStatus_Exception(status)) {
		if (error) {
			*error = QString::fromUtf8(status.err_msg
				? status.err_msg
				: "Could not initialize CPython");
		}
		setBridgePluginManager(nullptr);
		return false;
	}
	_private->ownsInterpreter = true;

	if (!PrependSysPath(runtimeRoot, error)
		|| !PrependSysPath(runtimeRoot + QStringLiteral("/sdk"), error)) {
		shutdown();
		return false;
	}

	_private->loaderModule = PyImport_ImportModule("loader");
	if (!_private->loaderModule) {
		if (error) {
			*error = PythonError();
		}
		shutdown();
		return false;
	}

	_private->initialized = true;
	return true;
#endif
}

void PythonRuntime::shutdown() {
#if defined(AYUGRAM_ENABLE_PYTHON_PLUGINS)
	if (_private->loaderModule) {
		auto *args = PyTuple_New(0);
		auto *result = CallLoader(_private->loaderModule, "unload_all", args);
		Py_XDECREF(result);
		Py_DECREF(args);
		if (PyErr_Occurred()) {
			PyErr_Clear();
		}

		Py_DECREF(_private->loaderModule);
		_private->loaderModule = nullptr;
	}

	_private->initialized = false;
	setBridgePluginManager(nullptr);
	if (_private->ownsInterpreter && Py_IsInitialized()) {
		Py_FinalizeEx();
	}
	_private->ownsInterpreter = false;
#else
	_private->initialized = false;
#endif
}

bool PythonRuntime::isInitialized() const {
	return _private->initialized;
}

PythonRuntime::LoadResult PythonRuntime::loadPlugin(const QString &path) {
	auto result = LoadResult();
#if !defined(AYUGRAM_ENABLE_PYTHON_PLUGINS)
	result.error = QStringLiteral("Python plugin support is disabled");
	return result;
#else
	if (!_private->initialized || !_private->loaderModule) {
		result.error = QStringLiteral("Python runtime is not initialized");
		return result;
	}

	const auto utf8 = QFileInfo(path).absoluteFilePath().toUtf8();
	auto *pyPath = PyUnicode_FromStringAndSize(utf8.constData(), utf8.size());
	if (!pyPath) {
		result.error = PythonError();
		return result;
	}
	auto *args = PyTuple_Pack(1, pyPath);
	Py_DECREF(pyPath);
	auto *loaded = CallLoader(_private->loaderModule, "load_plugin", args);
	Py_DECREF(args);
	if (!loaded) {
		result.error = PythonError();
		return result;
	}
	if (!PyDict_Check(loaded)) {
		Py_DECREF(loaded);
		result.error = QStringLiteral("loader.load_plugin() returned a non-dict value");
		return result;
	}

	result.metadata = PyToVariant(loaded).toMap();
	result.ok = true;
	Py_DECREF(loaded);
	return result;
#endif
}

bool PythonRuntime::unloadPlugin(const QString &pluginId, QString *error) {
#if !defined(AYUGRAM_ENABLE_PYTHON_PLUGINS)
	if (error) {
		*error = QStringLiteral("Python plugin support is disabled");
	}
	return false;
#else
	if (!_private->initialized || !_private->loaderModule) {
		if (error) {
			*error = QStringLiteral("Python runtime is not initialized");
		}
		return false;
	}

	const auto utf8 = pluginId.toUtf8();
	auto *id = PyUnicode_FromStringAndSize(utf8.constData(), utf8.size());
	auto *args = PyTuple_Pack(1, id);
	Py_DECREF(id);
	auto *result = CallLoader(_private->loaderModule, "unload_plugin", args);
	Py_DECREF(args);
	if (!result) {
		if (error) {
			*error = PythonError();
		}
		return false;
	}
	Py_DECREF(result);
	return true;
#endif
}

QStringList PythonRuntime::loadedPluginIds(QString *error) const {
	auto result = QStringList();
#if !defined(AYUGRAM_ENABLE_PYTHON_PLUGINS)
	if (error) {
		*error = QStringLiteral("Python plugin support is disabled");
	}
	return result;
#else
	if (!_private->initialized || !_private->loaderModule) {
		if (error) {
			*error = QStringLiteral("Python runtime is not initialized");
		}
		return result;
	}

	auto *args = PyTuple_New(0);
	auto *ids = CallLoader(_private->loaderModule, "loaded_plugin_ids", args);
	Py_DECREF(args);
	if (!ids) {
		if (error) {
			*error = PythonError();
		}
		return result;
	}
	if (!PyTuple_Check(ids) && !PyList_Check(ids)) {
		Py_DECREF(ids);
		if (error) {
			*error = QStringLiteral("loader.loaded_plugin_ids() returned invalid data");
		}
		return result;
	}

	const auto count = PySequence_Size(ids);
	for (Py_ssize_t i = 0; i < count; ++i) {
		auto *item = PySequence_GetItem(ids, i);
		if (item && PyUnicode_Check(item)) {
			result.push_back(PyString(item));
		}
		Py_XDECREF(item);
	}
	Py_DECREF(ids);
	return result;
#endif
}

} // namespace Ayu::Plugins
