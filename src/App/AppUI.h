#pragma once

#include <imgui.h>

#include <algorithm>
#include <cmath>

namespace s2gp
{
    // Standardized button widths so the toolbar reads as one coherent set.
    namespace UiSize
    {
        inline const ImVec2 InterfaceButtonSmall  = ImVec2( 64.0f, 0.0f);
        inline const ImVec2 InterfaceButtonMedium = ImVec2( 96.0f, 0.0f);
        inline const ImVec2 DialogButton          = ImVec2(108.0f, 0.0f);

        // Source-type dropdown width: fits the widest of Piano Sheet / Tab.
        inline float RowDropdownWidth()
        {
            const ImGuiStyle& s = ImGui::GetStyle();
            const float widest = ImGui::CalcTextSize("Piano Sheet").x;
            return widest + ImGui::GetFrameHeight() + s.FramePadding.x * 2.0f;
        }
    }

    namespace Ui
    {
        inline void CenterCursorX(float itemW)
        {
            ImGui::SetCursorPosX((ImGui::GetWindowSize().x - itemW) * 0.5f);
        }

        inline void RightAlignCursorX(float itemW)
        {
            ImGui::SetCursorPosX(ImGui::GetWindowContentRegionMax().x - itemW);
        }

        inline ImU32 ButtonBgColor(bool isHeld, bool isHovered)
        {
            return ImGui::GetColorU32(isHeld ? ImGuiCol_ButtonActive : isHovered ? ImGuiCol_ButtonHovered : ImGuiCol_Button);
        }

        // Self-drawn button shell. drawIcon(dl, pos, size, frameBg) paints
        // the foreground; frameBg is forwarded so it can carve inner shapes.
        template <typename DrawIcon>
        bool IconButton(const char* str_id, ImVec2 size, DrawIcon&& drawIcon)
        {
            const ImVec2 pos       = ImGui::GetCursorScreenPos();
            const bool   isClicked = ImGui::InvisibleButton(str_id, size);
            const bool   isHovered = ImGui::IsItemHovered();
            const bool   isHeld    = ImGui::IsItemActive();
            const ImU32  frameBg   = ButtonBgColor(isHeld, isHovered);

            ImDrawList* dl = ImGui::GetWindowDrawList();
            const ImVec2 br(pos.x + size.x, pos.y + size.y);
            dl->AddRectFilled(pos, br, frameBg, ImGui::GetStyle().FrameRounding);
            drawIcon(dl, pos, size, frameBg);
            return isClicked;
        }
    }
}
