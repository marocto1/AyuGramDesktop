#pragma once

namespace Ayu::Plugins {

class PluginManager;

bool registerPythonBridgeModule();
void setBridgePluginManager(PluginManager *manager);

} // namespace Ayu::Plugins
