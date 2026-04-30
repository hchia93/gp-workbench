@echo off
rem Reset CMake build state and IDE caches, then run the configure preset.
rem Works for both VS Open Folder and VS Code (CMake Tools) workflows --
rem CMakePresets.json is the single source of truth, this script just
rem wipes stale state and triggers configure.
rem
rem Requirements in the current shell:
rem   * cmake on PATH       (VS Developer Command Prompt has it bundled,
rem                          or install CMake standalone)
rem   * VCPKG_ROOT defined  (one-time: setx VCPKG_ROOT ^<path^>\vcpkg)

setlocal
pushd "%~dp0"

where cmake >nul 2>&1
if errorlevel 1 (
    echo [ERROR] cmake not found on PATH.
    echo Run this from a Visual Studio Developer Command Prompt, or install CMake standalone.
    popd
    exit /b 1
)

if not defined VCPKG_ROOT (
    echo [ERROR] VCPKG_ROOT is not set.
    echo Run once: setx VCPKG_ROOT ^<path^>\vcpkg  (then open a new shell^)
    popd
    exit /b 1
)

if exist .vs     rmdir /s /q .vs
if exist .vscode rmdir /s /q .vscode
if exist build   rmdir /s /q build

cmake --preset windows-x64
set EXIT=%errorlevel%

popd
exit /b %EXIT%
