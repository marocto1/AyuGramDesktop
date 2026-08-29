option(AYUGRAM_ENABLE_PYTHON_PLUGINS "Enable exteraGram/AyuGram .plugin runtime" OFF)

if (AYUGRAM_ENABLE_PYTHON_PLUGINS)
    find_package(Python3 3.11 EXACT COMPONENTS Development REQUIRED)

    target_sources(Telegram PRIVATE
        ${src_loc}/ayu/plugins/plugin_manager.cpp
        ${src_loc}/ayu/plugins/plugin_manager.h
        ${src_loc}/ayu/plugins/python_runtime.cpp
        ${src_loc}/ayu/plugins/python_runtime.h
        ${src_loc}/ayu/plugins/python_bridge.cpp
        ${src_loc}/ayu/plugins/python_bridge.h
    )

    target_compile_definitions(Telegram PRIVATE AYUGRAM_ENABLE_PYTHON_PLUGINS=1)
    target_link_libraries(Telegram PRIVATE Python3::Python)

    add_custom_command(TARGET Telegram POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E make_directory
            "$<TARGET_FILE_DIR:Telegram>/ayu_plugins/runtime"
        COMMAND ${CMAKE_COMMAND} -E copy_directory
            "${res_loc}/ayu_plugins/runtime"
            "$<TARGET_FILE_DIR:Telegram>/ayu_plugins/runtime"
        COMMENT "Copying AyuGram Python plugin runtime"
    )
endif()
