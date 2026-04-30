cmake_minimum_required(VERSION 3.24)

# CMP0135: use extraction time as timestamp for URL-fetched archives
# (NEW behavior, recommended for ExternalProject/FetchContent URL downloads)
if(POLICY CMP0135)
    cmake_policy(SET CMP0135 NEW)
endif()

project(score-pdf-to-gp VERSION 0.1.0 LANGUAGES CXX)

option(HIDE_CONSOLE "Hide console window on Windows GUI build" ON)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Allow FetchContent_Populate (deprecated in CMake 3.30 but still required to
# fetch source WITHOUT add_subdirectory'ing third-party CMakeLists files).
if(POLICY CMP0169)
    cmake_policy(SET CMP0169 OLD)
endif()

include(FetchContent)

# ImGui — populate source tree only, do NOT add_subdirectory.
# FetchContent_MakeAvailable would run ImGui's own root CMakeLists and pull in
# imgui_examples.sln + 16 example_*.vcxproj targets, cluttering the VS startup
# dropdown. We compile the ImGui .cpp files into the exe directly below.
FetchContent_Declare(
    imgui
    GIT_REPOSITORY https://github.com/ocornut/imgui
    GIT_TAG v1.90.7
)
FetchContent_GetProperties(imgui)
if(NOT imgui_POPULATED)
    FetchContent_Populate(imgui)
endif()

# ImGui ships hand-written .vcxproj / .sln files under examples/ for its own
# developer workflow. VS Open Folder scans the whole source tree and would
# surface them as startup targets in the dropdown (16 example_*.vcxproj +
# imgui_examples.sln). Strip them on every configure.
file(GLOB_RECURSE _imgui_legacy_vs_files
    "${imgui_SOURCE_DIR}/examples/*.vcxproj"
    "${imgui_SOURCE_DIR}/examples/*.vcxproj.filters"
    "${imgui_SOURCE_DIR}/examples/*.sln"
    "${imgui_SOURCE_DIR}/examples/*.slnx"
)
if(_imgui_legacy_vs_files)
    file(REMOVE ${_imgui_legacy_vs_files})
endif()

# PDFium prebuilt binaries (no source build, ~1s download).
# Populate-only: the URL has no CMakeLists anyway, but Populate also skips
# creating the pdfium-populate helper sub-solution that MakeAvailable produces.
set(PDFIUM_VERSION chromium/6721)
set(PDFIUM_URL https://github.com/bblanchon/pdfium-binaries/releases/download/${PDFIUM_VERSION}/pdfium-win-x64.tgz)
FetchContent_Declare(
    pdfium
    URL ${PDFIUM_URL}
)
FetchContent_GetProperties(pdfium)
if(NOT pdfium_POPULATED)
    FetchContent_Populate(pdfium)
endif()

# After every FetchContent_Populate, scrub the helper sub-build .vcxproj /
# .sln files. CMake regenerates them only when a Populate is actually
# triggered (i.e. -src missing), and our subsequent file(REMOVE) keeps the
# active VS session's dropdown clean. Leaves -src directories alone.
file(GLOB_RECURSE _fc_subbuild_vs_files
    "${FETCHCONTENT_BASE_DIR}/*-subbuild/*.vcxproj"
    "${FETCHCONTENT_BASE_DIR}/*-subbuild/*.vcxproj.filters"
    "${FETCHCONTENT_BASE_DIR}/*-subbuild/*.sln"
    "${FETCHCONTENT_BASE_DIR}/*-subbuild/*.slnx"
)
if(_fc_subbuild_vs_files)
    file(REMOVE ${_fc_subbuild_vs_files})
endif()

find_package(glfw3 CONFIG REQUIRED)
find_package(OpenGL REQUIRED)
find_package(pugixml CONFIG REQUIRED)
find_package(miniz CONFIG REQUIRED)

set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)

file(GLOB_RECURSE APP_SOURCES CONFIGURE_DEPENDS "src/*.cpp")
file(GLOB_RECURSE APP_HEADERS CONFIGURE_DEPENDS "src/*.h")

set(IMGUI_BACKEND_SOURCES
    ${imgui_SOURCE_DIR}/backends/imgui_impl_glfw.cpp
    ${imgui_SOURCE_DIR}/backends/imgui_impl_opengl3.cpp
)

file(GLOB IMGUI_CORE_SOURCES
    ${imgui_SOURCE_DIR}/imgui.cpp
    ${imgui_SOURCE_DIR}/imgui_draw.cpp
    ${imgui_SOURCE_DIR}/imgui_tables.cpp
    ${imgui_SOURCE_DIR}/imgui_widgets.cpp
    ${imgui_SOURCE_DIR}/imgui_demo.cpp
)

source_group("Source Files\\imgui" FILES ${IMGUI_CORE_SOURCES} ${IMGUI_BACKEND_SOURCES})

add_executable(${PROJECT_NAME}
    ${APP_SOURCES}
    ${APP_HEADERS}
    ${IMGUI_CORE_SOURCES}
    ${IMGUI_BACKEND_SOURCES}
)

target_link_libraries(${PROJECT_NAME} PRIVATE
    glfw
    OpenGL::GL
    pugixml::pugixml
    miniz::miniz
    ${pdfium_SOURCE_DIR}/lib/pdfium.dll.lib
    $<$<PLATFORM_ID:Windows>:shell32>
    $<$<PLATFORM_ID:Windows>:ole32>
)

target_compile_definitions(${PROJECT_NAME} PRIVATE
    IMGUI_IMPL_OPENGL_LOADER_GLAD
    IMGUI_DISABLE_OBSOLETE_FUNCTIONS
    IMGUI_DISABLE_OBSOLETE_KEYIO
)

target_include_directories(${PROJECT_NAME} PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${imgui_SOURCE_DIR}
    ${imgui_SOURCE_DIR}/backends
    ${pdfium_SOURCE_DIR}/include
)

if(WIN32)
    # Use a configure-time path; VS Open Folder mode does not evaluate
    # generator expressions OR MSBuild macros for VS_DEBUGGER_WORKING_DIRECTORY.
    # cwd = bin/ is fine: Windows resolves dlls from the exe's own directory
    # (bin/<Config>/), not from cwd.
    set_target_properties(${PROJECT_NAME} PROPERTIES
        VS_DEBUGGER_WORKING_DIRECTORY "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}"
    )
    if(HIDE_CONSOLE)
        set_target_properties(${PROJECT_NAME} PROPERTIES WIN32_EXECUTABLE TRUE)
    endif()

    # Make the app the default startup project in the generated .sln
    # (otherwise VS picks ALL_BUILD which cannot be launched).
    set_property(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
                 PROPERTY VS_STARTUP_PROJECT ${PROJECT_NAME})
endif()

# Copy PDFium runtime DLL next to the exe
add_custom_command(TARGET ${PROJECT_NAME} POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        ${pdfium_SOURCE_DIR}/bin/pdfium.dll
        $<TARGET_FILE_DIR:${PROJECT_NAME}>/pdfium.dll
)

# Seed the dev build's userdata/ from the source repo on first build so the
# running exe finds its persistent config in the same relative location it
# will live in the packaged install. Skips files that already exist so
# subsequent SaveConfig writes are NOT overwritten on rebuild.
add_custom_command(TARGET ${PROJECT_NAME} POST_BUILD
    COMMAND ${CMAKE_COMMAND}
        -DSRC=${CMAKE_CURRENT_SOURCE_DIR}/userdata
        -DDST=$<TARGET_FILE_DIR:${PROJECT_NAME}>/userdata
        -P  ${CMAKE_CURRENT_SOURCE_DIR}/cmake/SeedDirIfMissing.cmake
)

# ---- Install / package ----
# `cmake --install . --prefix <dir>` lays out the portable tree:
#   <prefix>/score-pdf-to-gp.exe
#   <prefix>/pdfium.dll
#   <prefix>/glfw3.dll
#   <prefix>/README.md
#   <prefix>/userdata/config.ini   <-- shipped baseline, edited in place
install(TARGETS ${PROJECT_NAME} RUNTIME DESTINATION .)
install(FILES     ${pdfium_SOURCE_DIR}/bin/pdfium.dll DESTINATION .)
install(IMPORTED_RUNTIME_ARTIFACTS glfw RUNTIME DESTINATION .)
install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/userdata DESTINATION .)

# CPack: zip artifact for GitHub releases.
set(CPACK_GENERATOR "ZIP")
set(CPACK_PACKAGE_NAME "score-pdf-to-gp")
set(CPACK_PACKAGE_VERSION ${PROJECT_VERSION})
set(CPACK_PACKAGE_FILE_NAME "score-pdf-to-gp-${PROJECT_VERSION}-win-x64")
set(CPACK_INCLUDE_TOPLEVEL_DIRECTORY OFF)
include(CPack)

message(STATUS "Project: ${PROJECT_NAME}")
message(STATUS "Version: ${PROJECT_VERSION}")
message(STATUS "C++ Standard: ${CMAKE_CXX_STANDARD}")
message(STATUS "PDFium: ${PDFIUM_VERSION}")
message(STATUS "Output Directory: ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}")
message(STATUS "Hide Console: ${HIDE_CONSOLE}")
