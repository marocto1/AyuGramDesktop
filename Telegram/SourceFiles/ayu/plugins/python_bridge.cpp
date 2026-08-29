#include "ayu/plugins/python_bridge.h"

#include "ayu/plugins/plugin_manager.h"

#if defined(AYUGRAM_ENABLE_PYTHON_PLUGINS)
#include <Python.h>
#endif

#include <QVariantList>

namespace Ayu::Plugins {
namespace {

PluginManager *gManager = nullptr;

#if defined(AYUGRAM_ENABLE_PYTHON_PLUGINS)

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
		const auto result = PyLong_AsLongLong(value);
		if (!PyErr_Occurred()) {
			return QVariant::fromValue<qlonglong>(result);
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
		auto list = QVariantList();
		const auto count = PySequence_Size(value);
		for (Py_ssize_t i = 0; i < count; ++i) {
			auto *item = PySequence_GetItem(value, i);
			list.push_back(PyToVariant(item));
			Py_XDECREF(item);
		}
		return list;
	}
	if (PyDict_Check(value)) {
		auto map = QVariantMap();
		PyObject *key = nullptr;
		PyObject *item = nullptr;
		Py_ssize_t pos = 0;
		while (PyDict_Next(value, &pos, &key, &item)) {
			if (PyUnicode_Check(key)) {
				map.insert(PyString(key), PyToVariant(item));
			}
		}
		return map;
	}
	return QVariant(QString::fromUtf8(Py_TYPE(value)->tp_name));
}

PyObject *VariantToPy(const QVariant &value) {
	if (!value.isValid() || value.isNull()) {
		Py_RETURN_NONE;
	}

	switch (value.metaType().id()) {
	case QMetaType::Bool:
		return PyBool_FromLong(value.toBool() ? 1 : 0);
	case QMetaType::Int:
	case QMetaType::LongLong:
	case QMetaType::UInt:
	case QMetaType::ULongLong:
		return PyLong_FromLongLong(value.toLongLong());
	case QMetaType::Double:
		return PyFloat_FromDouble(value.toDouble());
	case QMetaType::QString: {
		const auto utf8 = value.toString().toUtf8();
		return PyUnicode_FromStringAndSize(utf8.constData(), utf8.size());
	}
	default:
		break;
	}

	if (value.canConvert<QVariantList>()) {
		const auto list = value.toList();
		auto *result = PyList_New(list.size());
		for (qsizetype i = 0; i < list.size(); ++i) {
			PyList_SET_ITEM(result, i, VariantToPy(list[i]));
		}
		return result;
	}
	if (value.canConvert<QVariantMap>()) {
		auto *result = PyDict_New();
		const auto map = value.toMap();
		for (auto i = map.cbegin(), e = map.cend(); i != e; ++i) {
			auto *pyValue = VariantToPy(i.value());
			const auto key = i.key().toUtf8();
			PyDict_SetItemString(result, key.constData(), pyValue);
			Py_DECREF(pyValue);
		}
		return result;
	}

	const auto text = value.toString().toUtf8();
	return PyUnicode_FromStringAndSize(text.constData(), text.size());
}

bool RequireManager() {
	if (gManager) {
		return true;
	}
	PyErr_SetString(PyExc_RuntimeError, "AyuGram plugin manager is unavailable");
	return false;
}

PyObject *BridgeLog(PyObject *, PyObject *args) {
	PyObject *pluginObject = nullptr;
	PyObject *messageObject = nullptr;
	if (!PyArg_ParseTuple(args, "UU", &pluginObject, &messageObject)) {
		return nullptr;
	}
	if (!RequireManager()) {
		return nullptr;
	}
	gManager->log(PyString(pluginObject), PyString(messageObject));
	Py_RETURN_NONE;
}

PyObject *BridgeGetSetting(PyObject *, PyObject *args) {
	PyObject *pluginObject = nullptr;
	PyObject *keyObject = nullptr;
	PyObject *fallback = Py_None;
	if (!PyArg_ParseTuple(args, "UU|O", &pluginObject, &keyObject, &fallback)) {
		return nullptr;
	}
	if (!RequireManager()) {
		return nullptr;
	}
	return VariantToPy(gManager->getSetting(
		PyString(pluginObject),
		PyString(keyObject),
		PyToVariant(fallback)));
}

PyObject *BridgeSetSetting(PyObject *, PyObject *args) {
	PyObject *pluginObject = nullptr;
	PyObject *keyObject = nullptr;
	PyObject *valueObject = nullptr;
	int reloadSettings = 0;
	if (!PyArg_ParseTuple(
			args,
			"UUO|p",
			&pluginObject,
			&keyObject,
			&valueObject,
			&reloadSettings)) {
		return nullptr;
	}
	if (!RequireManager()) {
		return nullptr;
	}

	auto error = QString();
	if (!gManager->setSetting(
			PyString(pluginObject),
			PyString(keyObject),
			PyToVariant(valueObject),
			&error)) {
		PyErr_SetString(PyExc_RuntimeError, error.toUtf8().constData());
		return nullptr;
	}
	Q_UNUSED(reloadSettings);
	Py_RETURN_NONE;
}

PyObject *BridgeUnsupported(PyObject *, PyObject *args) {
	Q_UNUSED(args);
	PyErr_SetString(
		PyExc_NotImplementedError,
		"This plugin API surface is not implemented by the Desktop bridge yet");
	return nullptr;
}

PyObject *BridgeRunOnUiThread(PyObject *, PyObject *args) {
	PyObject *callback = nullptr;
	PyObject *callArgs = nullptr;
	PyObject *kwargs = nullptr;
	if (!PyArg_ParseTuple(args, "OOO", &callback, &callArgs, &kwargs)) {
		return nullptr;
	}
	if (!PyCallable_Check(callback)) {
		PyErr_SetString(PyExc_TypeError, "callback must be callable");
		return nullptr;
	}
	if (!PyTuple_Check(callArgs)) {
		PyErr_SetString(PyExc_TypeError, "args must be a tuple");
		return nullptr;
	}
	if (kwargs != Py_None && !PyDict_Check(kwargs)) {
		PyErr_SetString(PyExc_TypeError, "kwargs must be a dict or None");
		return nullptr;
	}
	return PyObject_Call(
		callback,
		callArgs,
		(kwargs == Py_None) ? nullptr : kwargs);
}

PyMethodDef kMethods[] = {
	{ "log", BridgeLog, METH_VARARGS, "Write a message to the AyuGram log." },
	{ "get_setting", BridgeGetSetting, METH_VARARGS, "Read plugin setting." },
	{ "set_setting", BridgeSetSetting, METH_VARARGS, "Persist plugin setting." },
	{ "register_hook", BridgeUnsupported, METH_VARARGS, nullptr },
	{ "register_send_message_hook", BridgeUnsupported, METH_VARARGS, nullptr },
	{ "remove_hook", BridgeUnsupported, METH_VARARGS, nullptr },
	{ "add_menu_item", BridgeUnsupported, METH_VARARGS, nullptr },
	{ "remove_menu_item", BridgeUnsupported, METH_VARARGS, nullptr },
	{ "client_call", BridgeUnsupported, METH_VARARGS, nullptr },
	{ "ui_call", BridgeUnsupported, METH_VARARGS, nullptr },
	{ "hook_call", BridgeUnsupported, METH_VARARGS, nullptr },
	{ "run_on_ui_thread", BridgeRunOnUiThread, METH_VARARGS, nullptr },
	{ nullptr, nullptr, 0, nullptr },
};

PyModuleDef kModule = {
	PyModuleDef_HEAD_INIT,
	"_ayugram_desktop",
	"AyuGram Desktop native plugin bridge.",
	-1,
	kMethods,
};

PyMODINIT_FUNC PyInit__ayugram_desktop() {
	return PyModule_Create(&kModule);
}

#endif

} // namespace

bool registerPythonBridgeModule() {
#if defined(AYUGRAM_ENABLE_PYTHON_PLUGINS)
	return PyImport_AppendInittab(
		"_ayugram_desktop",
		&PyInit__ayugram_desktop) == 0;
#else
	return false;
#endif
}

void setBridgePluginManager(PluginManager *manager) {
	gManager = manager;
}

} // namespace Ayu::Plugins
