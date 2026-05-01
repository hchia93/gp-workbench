#pragma once

#include <string>

#include "App/AppTheme.h"

namespace s2gp
{
    enum class SourceType : int
    {
        PianoSheet = 0,
        Tab,
    };

    class AppMainWindow
    {
    public:
        AppMainWindow();

        void Render();
        void ApplyImGuiStyle();

        // Must be called after ImGui::CreateContext() and before the first NewFrame().
        static void LoadFonts();

        // Drag-drop entry from GLFW callback. Only the first .pdf among the
        // dropped paths is taken; the rest are ignored.
        void OnFilesDropped(const char** paths, int count);

    private:
        void RenderInputRow();
        void RenderOutputPanel();
        void RenderPianoParamsPopup();
        void RenderNoticePopup();

        void Convert();
        void BrowseFolder();
        void PickInputFile();
        void LoadConfig();
        void SaveConfig();
        void ShowMessageDialog(std::string msg, std::string buttonLabel = "OK");

        std::string m_InputPath;
        SourceType  m_SourceType            = SourceType::PianoSheet;

        char        m_OutputDir[1024]       = {};
        char        m_OutputFile[256]       = {};

        bool        m_PianoParamsRequested  = false;

        std::string m_NoticeMessage;
        std::string m_NoticeButton          = "OK";
        bool        m_NoticeRequested       = false;

        ThemeId     m_Theme                 = ThemeId::PhotoshopDark;
    };
}
