#pragma once

#include "settings/settings_common_session.h"

#include <QJsonObject>

namespace Ui {
class InputField;
class VerticalLayout;
}

namespace Settings {

class ExteraMain final : public Section<ExteraMain> {
public:
	ExteraMain(QWidget *parent, not_null<Window::SessionController*> controller);
	[[nodiscard]] rpl::producer<QString> title() override;

};

class ExteraPlugins final : public Section<ExteraPlugins> {
public:
	ExteraPlugins(QWidget *parent, not_null<Window::SessionController*> controller);
	[[nodiscard]] rpl::producer<QString> title() override;

private:
	void refresh();
	void importPlugin();
	void showSettings(QJsonObject plugin);
	void command(QJsonObject request, Fn<void(QJsonObject)> done = nullptr);

	not_null<Window::SessionController*> _controller;
	Ui::VerticalLayout *_list = nullptr;
	Ui::InputField *_search = nullptr;

};

}
