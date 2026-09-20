#include "extera/settings_extera.h"

#include "extera/plugin_manager.h"
#include "ayu/ui/settings/settings_appearance.h"
#include "ayu/ui/settings/settings_chats.h"
#include "ayu/ui/settings/settings_general.h"
#include "ayu/ui/settings/settings_other.h"
#include "core/file_utilities.h"
#include "core/version.h"
#include "lang_auto.h"
#include "settings/sections/settings_main.h"
#include "settings/settings_builder.h"
#include "styles/style_layers.h"
#include "styles/style_menu_icons.h"
#include "styles/style_settings.h"
#include "ui/boxes/confirm_box.h"
#include "ui/boxes/single_choice_box.h"
#include "ui/layers/generic_box.h"
#include "ui/vertical_list.h"
#include "ui/widgets/buttons.h"
#include "ui/widgets/fields/input_field.h"
#include "ui/widgets/labels.h"
#include "ui/wrap/vertical_layout.h"
#include "window/window_session_controller.h"

#include <QDesktopServices>
#include <QJsonArray>
#include <QUrl>

namespace Settings {
namespace {

using namespace Builder;

void AddText(not_null<Ui::VerticalLayout*> parent, QString text) {
	parent->add(object_ptr<Ui::FlatLabel>(
		parent, std::move(text), st::boxLabel), st::boxRowPadding);
}

const auto kMainMeta = BuildHelper({
	.id = ExteraMain::Id(),
	.parentId = MainId(),
	.title = &tr::lng_extera_title,
	.icon = &st::menuIconFave,
}, [](SectionBuilder &builder) {
	builder.addSkip();
	builder.add([](const WidgetContext &ctx) -> SectionBuilder::WidgetToAdd {
		return {
			.widget = object_ptr<Ui::FlatLabel>(ctx.container,
				u"ExteraGram Desktop · "_q + QString::fromLatin1(AppVersionStr),
				st::boxTitle),
			.align = style::al_top,
		};
	});
	builder.addDividerText(tr::lng_extera_about());
	builder.addSubsectionTitle(tr::ayu_CategoriesHeader());
	builder.addSectionButton({
		.title = tr::ayu_CategoryGeneral(),
		.targetSection = AyuGeneral::Id(),
		.icon = { &st::menuIconShowAll },
	});
	builder.addSectionButton({
		.title = tr::ayu_CategoryAppearance(),
		.targetSection = AyuAppearance::Id(),
		.icon = { &st::menuIconPalette },
	});
	builder.addSectionButton({
		.title = tr::ayu_CategoryChats(),
		.targetSection = AyuChats::Id(),
		.icon = { &st::menuIconChatBubble },
	});
	builder.addSectionButton({
		.title = tr::lng_extera_plugins(),
		.targetSection = ExteraPlugins::Id(),
		.icon = { &st::menuIconBot },
		.keywords = { u"plugin"_q, u".plugin"_q, u"python"_q },
	});
	builder.addSectionButton({
		.title = tr::ayu_CategoryOther(),
		.targetSection = AyuOther::Id(),
		.icon = { &st::menuIconFave },
	});
	builder.addSkip();
	builder.addDivider();
	builder.addSubsectionTitle(tr::ayu_LinksHeader());
	builder.addButton({
		.title = tr::ayu_LinksDocumentation(),
		.icon = { &st::menuIconIpAddress },
		.label = rpl::single(u"Desktop API 1"_q),
		.onClick = [] {
			QDesktopServices::openUrl(QUrl(
				u"https://github.com/airgram-real/ExteraGramDesktop/blob/dev/docs/extera-plugins.md"_q));
		},
	});
	builder.addButton({
		.title = rpl::single(u"exteraGram · Android SDK"_q),
		.icon = { &st::menuIconLink },
		.onClick = [] {
			QDesktopServices::openUrl(QUrl(u"https://plugins.exteragram.app/docs"_q));
		},
	});
	builder.addSkip();
});

const auto kPluginsMeta = BuildHelper({
	.id = ExteraPlugins::Id(),
	.parentId = ExteraMain::Id(),
	.title = &tr::lng_extera_plugins,
	.icon = &st::menuIconBot,
}, [](SectionBuilder &builder) {
	builder.addDividerText(tr::lng_extera_warning());
});

}

ExteraMain::ExteraMain(
	QWidget *parent,
	not_null<Window::SessionController*> controller)
: Section(parent, controller) {
	const auto content = Ui::CreateChild<Ui::VerticalLayout>(this);
	build(content, kMainMeta.build);
	Ui::ResizeFitChild(this, content);
}

rpl::producer<QString> ExteraMain::title() {
	return tr::lng_extera_title();
}

ExteraPlugins::ExteraPlugins(
	QWidget *parent,
	not_null<Window::SessionController*> controller)
: Section(parent, controller)
, _controller(controller) {
	const auto content = Ui::CreateChild<Ui::VerticalLayout>(this);
	build(content, kPluginsMeta.build);
	auto &manager = Extera::PluginManager::Instance();
	manager.start();
	const auto engine = content->add(object_ptr<Ui::SettingsButton>(
		content, tr::lng_extera_engine(), st::settingsButton));
	engine->toggleOn(rpl::single(rpl::empty_value()) | rpl::then(manager.changes())
		| rpl::map([=] {
			return Extera::PluginManager::Instance().snapshot().value(u"engine"_q).toBool();
		}), true);
	engine->addClickHandler([=] {
		auto &manager = Extera::PluginManager::Instance();
		const auto enabled = manager.snapshot().value(u"engine"_q).toBool();
		const auto enable = crl::guard(this, [=] {
			command({ { u"op"_q, u"engine"_q }, { u"value"_q, true } });
		});
		if (enabled) {
			command({ { u"op"_q, u"engine"_q }, { u"value"_q, false } });
		} else {
			_controller->show(Ui::MakeConfirmBox({
				.text = tr::lng_extera_warning(),
				.confirmed = [=](Fn<void()> &&close) { close(); enable(); },
				.confirmText = tr::lng_extera_enable(),
			}));
		}
	});
	const auto install = content->add(object_ptr<Ui::SettingsButton>(
		content, tr::lng_extera_import(), st::settingsButton));
	install->addClickHandler([=] { importPlugin(); });
	const auto folder = content->add(object_ptr<Ui::SettingsButton>(
		content, tr::lng_extera_folder(), st::settingsButton));
	folder->addClickHandler([=] {
		QDesktopServices::openUrl(QUrl::fromLocalFile(
			Extera::PluginManager::Instance().directory()));
	});
	const auto restart = content->add(object_ptr<Ui::SettingsButton>(
		content, tr::lng_extera_refresh(), st::settingsButton));
	restart->addClickHandler([=] {
		Extera::PluginManager::Instance().start();
		command({ { u"op"_q, u"list"_q } });
	});
	_search = content->add(object_ptr<Ui::InputField>(
		content, st::settingsAddReplyField, tr::lng_extera_search()),
		st::boxRowPadding);
	_search->setMaxLength(128);
	_search->changes() | rpl::on_next([=] { refresh(); }, lifetime());
	_list = content->add(object_ptr<Ui::VerticalLayout>(content));
	manager.changes() | rpl::on_next([=] {
		crl::on_main(this, [=] { refresh(); });
	}, lifetime());
	refresh();
	Ui::ResizeFitChild(this, content);
}

rpl::producer<QString> ExteraPlugins::title() {
	return tr::lng_extera_plugins();
}

void ExteraPlugins::command(QJsonObject request, Fn<void(QJsonObject)> done) {
	Extera::PluginManager::Instance().request(std::move(request),
		crl::guard(this, [=](QJsonObject result) {
			if (!result.value(u"ok"_q).toBool()) {
				_controller->showToast(result.value(u"error"_q).toString());
			} else if (done) {
				done(result);
			}
		}));
}

void ExteraPlugins::importPlugin() {
	FileDialog::GetOpenPath(this, tr::lng_extera_import(tr::now),
		u"Python plugins (*.plugin)"_q,
		crl::guard(this, [=](const FileDialog::OpenResult &result) {
			if (!result.paths.empty()) {
				command({ { u"op"_q, u"install"_q }, { u"path"_q, result.paths.front() } });
			}
		}));
}

void ExteraPlugins::refresh() {
	if (!_list) {
		return;
	}
	_list->clear();
	auto &manager = Extera::PluginManager::Instance();
	const auto state = manager.snapshot();
	const auto warning = state.value(u"warning"_q).toString();
	if (!manager.error().isEmpty()) {
		AddText(_list, manager.error());
	}
	if (!warning.isEmpty()) {
		AddText(_list, warning);
	}
	const auto filter = _search->getLastText().trimmed();
	auto count = 0;
	for (const auto &value : state.value(u"plugins"_q).toArray()) {
		const auto plugin = value.toObject();
		const auto id = plugin.value(u"id"_q).toString();
		const auto name = plugin.value(u"name"_q).toString();
		const auto author = plugin.value(u"author"_q).toString();
		if (!(name + ' ' + author + ' ' + id).contains(filter, Qt::CaseInsensitive)) {
			continue;
		}
		++count;
		Ui::AddDivider(_list);
		const auto enabled = plugin.value(u"enabled"_q).toBool();
		const auto compatible = plugin.value(u"compatible"_q).toBool();
		const auto button = _list->add(object_ptr<Ui::SettingsButton>(
			_list, rpl::single(name), st::settingsButton));
		button->toggleOn(rpl::single(enabled && manager.ready()
			&& plugin.value(u"active"_q).toBool()), true);
		button->setDisabled(!manager.ready() || !compatible);
		button->addClickHandler([=] {
			const auto apply = crl::guard(this, [=] {
				command({ { u"op"_q, u"enable"_q }, { u"plugin"_q, id },
					{ u"value"_q, !enabled } });
			});
			if (enabled) {
				apply();
			} else {
				_controller->show(Ui::MakeConfirmBox({
					.text = tr::lng_extera_warning(),
					.confirmed = [=](Fn<void()> &&close) { close(); apply(); },
					.confirmText = tr::lng_extera_enable(),
				}));
			}
		});
		AddText(_list, plugin.value(u"version"_q).toString() + u" · "_q + author);
		AddText(_list, plugin.value(u"description"_q).toString());
		if (!compatible) {
			AddText(_list, tr::lng_extera_incompatible(tr::now)
				+ '\n' + plugin.value(u"reason"_q).toString());
		}
		if (!plugin.value(u"error"_q).toString().isEmpty()) {
			AddText(_list, plugin.value(u"error"_q).toString());
		}
		const auto settings = _list->add(object_ptr<Ui::SettingsButton>(
			_list, tr::lng_settings_title(), st::settingsButton));
		settings->setDisabled(!manager.ready() || !plugin.value(u"active"_q).toBool());
		settings->addClickHandler([=] { showSettings(plugin); });
		const auto pinned = plugin.value(u"pinned"_q).toBool();
		const auto pin = _list->add(object_ptr<Ui::SettingsButton>(
			_list, pinned ? tr::lng_extera_unpin() : tr::lng_extera_pin(), st::settingsButton));
		pin->addClickHandler([=] {
			command({ { u"op"_q, u"pin"_q }, { u"plugin"_q, id }, { u"value"_q, !pinned } });
		});
		const auto remove = _list->add(object_ptr<Ui::SettingsButton>(
			_list, tr::lng_box_remove(), st::settingsButton));
		remove->addClickHandler([=] {
			const auto apply = crl::guard(this, [=] {
				command({ { u"op"_q, u"remove"_q }, { u"plugin"_q, id } });
			});
			_controller->show(Ui::MakeConfirmBox({
				.text = tr::lng_extera_remove_confirm(),
				.confirmed = [=](Fn<void()> &&close) { close(); apply(); },
				.confirmText = tr::lng_box_remove(),
			}));
		});
		Ui::AddSkip(_list);
	}
	if (!count) {
		AddText(_list, tr::lng_extera_empty(tr::now));
	}
}

void ExteraPlugins::showSettings(QJsonObject plugin) {
	const auto id = plugin.value(u"id"_q).toString();
	const auto name = plugin.value(u"name"_q).toString();
	command({ { u"op"_q, u"settings"_q }, { u"plugin"_q, id } },
		[=](QJsonObject result) {
			_controller->show(Box([=](not_null<Ui::GenericBox*> box) {
				box->setTitle(rpl::single(name));
				for (const auto &value : result.value(u"settings"_q).toArray()) {
					const auto row = value.toObject();
					const auto type = row.value(u"type"_q).toString();
					const auto text = row.value(u"text"_q).toString();
					const auto key = row.value(u"key"_q).toString();
					const auto save = crl::guard(this, [=](QJsonValue value) {
						command({ { u"op"_q, u"set_setting"_q }, { u"plugin"_q, id },
							{ u"key"_q, key }, { u"value"_q, value } });
					});
					if (type == u"Input"_q) {
						box->addRow(object_ptr<Ui::FlatLabel>(box, text, st::boxLabel));
						const auto field = box->addRow(object_ptr<Ui::InputField>(
							box, st::settingsAddReplyField, rpl::single(text),
							row.value(u"value"_q).toString()));
						field->setMaxLength(4096);
						const auto apply = box->addRow(object_ptr<Ui::SettingsButton>(
							box, tr::lng_settings_save(), st::settingsButton));
						apply->addClickHandler([=] { save(field->getLastText()); });
					} else if (type == u"Switch"_q) {
						const auto state = box->lifetime().make_state<rpl::variable<bool>>(
							row.value(u"value"_q).toBool());
						const auto toggle = box->addRow(object_ptr<Ui::SettingsButton>(
							box, rpl::single(text), st::settingsButton));
						toggle->toggleOn(state->value(), true);
						toggle->addClickHandler(crl::guard(this, [=] {
							const auto next = !state->current();
							command({ { u"op"_q, u"set_setting"_q }, { u"plugin"_q, id },
								{ u"key"_q, key }, { u"value"_q, next } },
								crl::guard(box, [=](QJsonObject) { *state = next; }));
						}));
					} else if (type == u"Selector"_q) {
						const auto select = box->addRow(object_ptr<Ui::SettingsButton>(
							box, rpl::single(text), st::settingsButton));
						select->addClickHandler(crl::guard(this, [=] {
							auto options = std::vector<QString>();
							for (const auto &item : row.value(u"items"_q).toArray()) {
								options.push_back(item.toString());
							}
							_controller->show(Box([=](not_null<Ui::GenericBox*> choice) {
								SingleChoiceBox(choice, {
									.title = rpl::single(text),
									.options = options,
									.initialSelection = row.value(u"value"_q).toInt(),
									.callback = [=](int index) { save(index); },
								});
							}));
						}));
					} else {
						box->addRow(object_ptr<Ui::FlatLabel>(box, text, st::boxLabel));
					}
				}
				box->addButton(tr::lng_close(), [=] { box->closeBox(); });
			}));
		});
}

}
