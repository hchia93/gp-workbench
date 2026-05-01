#include "App/AppTheme.h"

#include <imgui.h>

#include <cstring>

namespace s2gp
{
    const ThemeInfo kThemes[] = {
        { ThemeId::PhotoshopDark, "Photoshop Dark", "photoshop_dark" },
        { ThemeId::Walnut,        "Walnut",         "walnut"         },
        { ThemeId::Monokai,       "Monokai",        "monokai"        },
        { ThemeId::ImGuiDark,     "ImGui Dark",     "imgui_dark"     },
    };
    const int kThemeCount = static_cast<int>(sizeof(kThemes) / sizeof(kThemes[0]));

    namespace
    {
        inline ImVec4 RGB(int r, int g, int b, float a = 1.0f)
        {
            return ImVec4(r / 255.0f, g / 255.0f, b / 255.0f, a);
        }
        inline ImVec4 Alpha(ImVec4 v, float a)
        {
            return ImVec4(v.x, v.y, v.z, a);
        }

        // ---- Photoshop Dark / Graphite -------------------------------------
        // Pure neutral grays, no color cast. Big steps between bg / frame /
        // hover / active so widgets read clearly against the panel.
        void ApplyPhotoshopDark()
        {
            ImVec4* c = ImGui::GetStyle().Colors;

            const ImVec4 bgPit   = RGB( 16,  16,  16); // popup / scrollbar trough
            const ImVec4 bgDeep  = RGB( 26,  26,  26); // title bar / menu bar
            const ImVec4 bg      = RGB( 43,  43,  43); // window
            const ImVec4 bgLift  = RGB( 56,  56,  56); // child highlight
            const ImVec4 frame   = RGB( 70,  70,  70);
            const ImVec4 frameH  = RGB( 92,  92,  92);
            const ImVec4 frameA  = RGB(120, 120, 120);
            const ImVec4 border  = RGB( 82,  82,  82);
            const ImVec4 text    = RGB(240, 240, 240);
            const ImVec4 textDim = RGB(140, 140, 140);
            const ImVec4 selBg   = RGB( 80,  80,  80);
            const ImVec4 selH    = RGB(105, 105, 105);
            const ImVec4 selA    = RGB(135, 135, 135);
            const ImVec4 grip    = RGB(180, 180, 180);

            c[ImGuiCol_Text]                  = text;
            c[ImGuiCol_TextDisabled]          = textDim;
            c[ImGuiCol_WindowBg]              = bg;
            c[ImGuiCol_ChildBg]               = ImVec4(0,0,0,0);
            c[ImGuiCol_PopupBg]               = bgPit;
            c[ImGuiCol_Border]                = border;
            c[ImGuiCol_BorderShadow]          = ImVec4(0,0,0,0);
            c[ImGuiCol_FrameBg]               = frame;
            c[ImGuiCol_FrameBgHovered]        = frameH;
            c[ImGuiCol_FrameBgActive]         = frameA;
            c[ImGuiCol_TitleBg]               = bgDeep;
            c[ImGuiCol_TitleBgActive]         = bg;
            c[ImGuiCol_TitleBgCollapsed]      = bgPit;
            c[ImGuiCol_MenuBarBg]             = bgDeep;
            c[ImGuiCol_ScrollbarBg]           = bgPit;
            c[ImGuiCol_ScrollbarGrab]         = frame;
            c[ImGuiCol_ScrollbarGrabHovered]  = frameH;
            c[ImGuiCol_ScrollbarGrabActive]   = frameA;
            c[ImGuiCol_CheckMark]             = grip;
            c[ImGuiCol_SliderGrab]            = grip;
            c[ImGuiCol_SliderGrabActive]      = text;
            c[ImGuiCol_Button]                = frame;
            c[ImGuiCol_ButtonHovered]         = frameH;
            c[ImGuiCol_ButtonActive]          = frameA;
            c[ImGuiCol_Header]                = selBg;
            c[ImGuiCol_HeaderHovered]         = selH;
            c[ImGuiCol_HeaderActive]          = selA;
            c[ImGuiCol_Separator]             = border;
            c[ImGuiCol_SeparatorHovered]      = frameH;
            c[ImGuiCol_SeparatorActive]       = frameA;
            c[ImGuiCol_ResizeGrip]            = Alpha(border, 0.40f);
            c[ImGuiCol_ResizeGripHovered]     = Alpha(frameH, 0.70f);
            c[ImGuiCol_ResizeGripActive]      = Alpha(frameA, 0.90f);
            c[ImGuiCol_Tab]                   = bgLift;
            c[ImGuiCol_TabHovered]            = frameH;
            c[ImGuiCol_TabActive]             = frame;
            c[ImGuiCol_TabUnfocused]          = bgDeep;
            c[ImGuiCol_TabUnfocusedActive]    = bgLift;
            c[ImGuiCol_PlotLines]             = grip;
            c[ImGuiCol_PlotLinesHovered]      = text;
            c[ImGuiCol_PlotHistogram]         = grip;
            c[ImGuiCol_PlotHistogramHovered]  = text;
            c[ImGuiCol_TableHeaderBg]         = bgLift;
            c[ImGuiCol_TableBorderStrong]     = border;
            c[ImGuiCol_TableBorderLight]      = frame;
            c[ImGuiCol_TableRowBg]            = ImVec4(0,0,0,0);
            c[ImGuiCol_TableRowBgAlt]         = Alpha(bgLift, 0.40f);
            c[ImGuiCol_TextSelectedBg]        = Alpha(grip, 0.35f);
            c[ImGuiCol_DragDropTarget]        = Alpha(text, 0.90f);
            c[ImGuiCol_NavHighlight]          = text;
            c[ImGuiCol_NavWindowingHighlight] = Alpha(text, 0.70f);
            c[ImGuiCol_NavWindowingDimBg]     = ImVec4(0, 0, 0, 0.55f);
            c[ImGuiCol_ModalWindowDimBg]      = ImVec4(0, 0, 0, 0.55f);
        }

        // Walnut — warm dark brown + copper-amber accents.
        void ApplyWalnut()
        {
            ImVec4* c = ImGui::GetStyle().Colors;

            const ImVec4 bgPit   = RGB( 18,  14,  10);
            const ImVec4 bgDeep  = RGB( 26,  21,  16);
            const ImVec4 bg      = RGB( 38,  31,  24);
            const ImVec4 bgLift  = RGB( 52,  43,  34);
            const ImVec4 frame   = RGB( 70,  58,  46);
            const ImVec4 frameH  = RGB( 96,  79,  62);
            const ImVec4 frameA  = RGB(122, 100,  78);
            const ImVec4 border  = RGB( 86,  72,  56);
            const ImVec4 text    = RGB(242, 232, 216);
            const ImVec4 textDim = RGB(146, 132, 114);
            const ImVec4 amber   = RGB(214, 145,  62);
            const ImVec4 amberH  = RGB(232, 168,  88);
            const ImVec4 amberA  = RGB(250, 192, 116);
            const ImVec4 ember   = RGB(196,  82,  60);

            c[ImGuiCol_Text]                  = text;
            c[ImGuiCol_TextDisabled]          = textDim;
            c[ImGuiCol_WindowBg]              = bg;
            c[ImGuiCol_ChildBg]               = ImVec4(0,0,0,0);
            c[ImGuiCol_PopupBg]               = bgPit;
            c[ImGuiCol_Border]                = border;
            c[ImGuiCol_BorderShadow]          = ImVec4(0,0,0,0);
            c[ImGuiCol_FrameBg]               = frame;
            c[ImGuiCol_FrameBgHovered]        = frameH;
            c[ImGuiCol_FrameBgActive]         = frameA;
            c[ImGuiCol_TitleBg]               = bgDeep;
            c[ImGuiCol_TitleBgActive]         = bg;
            c[ImGuiCol_TitleBgCollapsed]      = bgPit;
            c[ImGuiCol_MenuBarBg]             = bgDeep;
            c[ImGuiCol_ScrollbarBg]           = bgPit;
            c[ImGuiCol_ScrollbarGrab]         = frame;
            c[ImGuiCol_ScrollbarGrabHovered]  = frameH;
            c[ImGuiCol_ScrollbarGrabActive]   = amber;
            c[ImGuiCol_CheckMark]             = amber;
            c[ImGuiCol_SliderGrab]            = amber;
            c[ImGuiCol_SliderGrabActive]      = amberA;
            c[ImGuiCol_Button]                = frame;
            c[ImGuiCol_ButtonHovered]         = frameH;
            c[ImGuiCol_ButtonActive]          = amber;
            c[ImGuiCol_Header]                = Alpha(amber, 0.45f);
            c[ImGuiCol_HeaderHovered]         = Alpha(amber, 0.65f);
            c[ImGuiCol_HeaderActive]          = amber;
            c[ImGuiCol_Separator]             = border;
            c[ImGuiCol_SeparatorHovered]      = amberH;
            c[ImGuiCol_SeparatorActive]       = amber;
            c[ImGuiCol_ResizeGrip]            = Alpha(border, 0.40f);
            c[ImGuiCol_ResizeGripHovered]     = Alpha(amberH, 0.70f);
            c[ImGuiCol_ResizeGripActive]      = Alpha(amber, 0.90f);
            c[ImGuiCol_Tab]                   = bgLift;
            c[ImGuiCol_TabHovered]            = frameH;
            c[ImGuiCol_TabActive]             = frame;
            c[ImGuiCol_TabUnfocused]          = bgDeep;
            c[ImGuiCol_TabUnfocusedActive]    = bgLift;
            c[ImGuiCol_PlotLines]             = amberH;
            c[ImGuiCol_PlotLinesHovered]      = amberA;
            c[ImGuiCol_PlotHistogram]         = amber;
            c[ImGuiCol_PlotHistogramHovered]  = ember;
            c[ImGuiCol_TableHeaderBg]         = bgLift;
            c[ImGuiCol_TableBorderStrong]     = border;
            c[ImGuiCol_TableBorderLight]      = frame;
            c[ImGuiCol_TableRowBg]            = ImVec4(0,0,0,0);
            c[ImGuiCol_TableRowBgAlt]         = Alpha(bgLift, 0.40f);
            c[ImGuiCol_TextSelectedBg]        = Alpha(amber, 0.35f);
            c[ImGuiCol_DragDropTarget]        = Alpha(ember, 0.90f);
            c[ImGuiCol_NavHighlight]          = amber;
            c[ImGuiCol_NavWindowingHighlight] = Alpha(text, 0.70f);
            c[ImGuiCol_NavWindowingDimBg]     = ImVec4(0, 0, 0, 0.55f);
            c[ImGuiCol_ModalWindowDimBg]      = ImVec4(0, 0, 0, 0.55f);
        }

        // ---- Monokai Pro ---------------------------------------------------
        // Warm dark grey with vivid orange / pink / yellow accents.
        void ApplyMonokai()
        {
            ImVec4* c = ImGui::GetStyle().Colors;

            const ImVec4 bgPit   = RGB( 22,  20,  23);
            const ImVec4 bgDeep  = RGB( 31,  29,  32);
            const ImVec4 bg      = RGB( 45,  42,  46);
            const ImVec4 bgLift  = RGB( 60,  57,  61);
            const ImVec4 frame   = RGB( 73,  71,  75);
            const ImVec4 frameH  = RGB(100,  97, 102);
            const ImVec4 frameA  = RGB(135, 132, 137);
            const ImVec4 border  = RGB( 92,  89,  94);
            const ImVec4 text    = RGB(252, 252, 250);
            const ImVec4 textDim = RGB(160, 158, 161);
            const ImVec4 orange  = RGB(253, 147,  83);
            const ImVec4 pink    = RGB(255,  97, 136);
            const ImVec4 yellow  = RGB(255, 216, 102);
            const ImVec4 green   = RGB(169, 220, 118);

            c[ImGuiCol_Text]                  = text;
            c[ImGuiCol_TextDisabled]          = textDim;
            c[ImGuiCol_WindowBg]              = bg;
            c[ImGuiCol_ChildBg]               = ImVec4(0,0,0,0);
            c[ImGuiCol_PopupBg]               = bgPit;
            c[ImGuiCol_Border]                = border;
            c[ImGuiCol_BorderShadow]          = ImVec4(0,0,0,0);
            c[ImGuiCol_FrameBg]               = frame;
            c[ImGuiCol_FrameBgHovered]        = frameH;
            c[ImGuiCol_FrameBgActive]         = frameA;
            c[ImGuiCol_TitleBg]               = bgDeep;
            c[ImGuiCol_TitleBgActive]         = bg;
            c[ImGuiCol_TitleBgCollapsed]      = bgPit;
            c[ImGuiCol_MenuBarBg]             = bgDeep;
            c[ImGuiCol_ScrollbarBg]           = bgPit;
            c[ImGuiCol_ScrollbarGrab]         = frame;
            c[ImGuiCol_ScrollbarGrabHovered]  = frameH;
            c[ImGuiCol_ScrollbarGrabActive]   = orange;
            c[ImGuiCol_CheckMark]             = orange;
            c[ImGuiCol_SliderGrab]            = orange;
            c[ImGuiCol_SliderGrabActive]      = yellow;
            c[ImGuiCol_Button]                = frame;
            c[ImGuiCol_ButtonHovered]         = frameH;
            c[ImGuiCol_ButtonActive]          = orange;
            c[ImGuiCol_Header]                = Alpha(orange, 0.40f);
            c[ImGuiCol_HeaderHovered]         = Alpha(orange, 0.60f);
            c[ImGuiCol_HeaderActive]          = orange;
            c[ImGuiCol_Separator]             = border;
            c[ImGuiCol_SeparatorHovered]      = orange;
            c[ImGuiCol_SeparatorActive]       = yellow;
            c[ImGuiCol_ResizeGrip]            = Alpha(border, 0.40f);
            c[ImGuiCol_ResizeGripHovered]     = Alpha(orange, 0.70f);
            c[ImGuiCol_ResizeGripActive]      = Alpha(yellow, 0.90f);
            c[ImGuiCol_Tab]                   = bgLift;
            c[ImGuiCol_TabHovered]            = frameH;
            c[ImGuiCol_TabActive]             = frame;
            c[ImGuiCol_TabUnfocused]          = bgDeep;
            c[ImGuiCol_TabUnfocusedActive]    = bgLift;
            c[ImGuiCol_PlotLines]             = pink;
            c[ImGuiCol_PlotLinesHovered]      = yellow;
            c[ImGuiCol_PlotHistogram]         = orange;
            c[ImGuiCol_PlotHistogramHovered]  = green;
            c[ImGuiCol_TableHeaderBg]         = bgLift;
            c[ImGuiCol_TableBorderStrong]     = border;
            c[ImGuiCol_TableBorderLight]      = frame;
            c[ImGuiCol_TableRowBg]            = ImVec4(0,0,0,0);
            c[ImGuiCol_TableRowBgAlt]         = Alpha(bgLift, 0.40f);
            c[ImGuiCol_TextSelectedBg]        = Alpha(orange, 0.35f);
            c[ImGuiCol_DragDropTarget]        = Alpha(pink, 0.90f);
            c[ImGuiCol_NavHighlight]          = orange;
            c[ImGuiCol_NavWindowingHighlight] = Alpha(text, 0.70f);
            c[ImGuiCol_NavWindowingDimBg]     = ImVec4(0, 0, 0, 0.55f);
            c[ImGuiCol_ModalWindowDimBg]      = ImVec4(0, 0, 0, 0.55f);
        }
    }

    void ApplyTheme(ThemeId id)
    {
        ImGui::StyleColorsDark();

        switch (id)
        {
            case ThemeId::PhotoshopDark: ApplyPhotoshopDark(); break;
            case ThemeId::Walnut:        ApplyWalnut();        break;
            case ThemeId::Monokai:       ApplyMonokai();       break;
            case ThemeId::ImGuiDark:     /* baseline */        break;
        }
    }

    ThemeId ThemeFromKey(const char* key)
    {
        if (!key || !*key)
        {
            return kThemes[0].id;
        }
        for (int i = 0; i < kThemeCount; ++i)
        {
            if (std::strcmp(key, kThemes[i].configKey) == 0)
            {
                return kThemes[i].id;
            }
        }
        return kThemes[0].id;
    }

    const char* ThemeKey(ThemeId id)
    {
        for (int i = 0; i < kThemeCount; ++i)
        {
            if (kThemes[i].id == id)
            {
                return kThemes[i].configKey;
            }
        }
        return kThemes[0].configKey;
    }
}
