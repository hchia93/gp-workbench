#include "App/AppMainWindow.h"

#include "App/AppUI.h"

#include <imgui.h>

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <string>

#ifdef _WIN32
  #define WIN32_LEAN_AND_MEAN
  #define NOMINMAX
  #include <windows.h>
  #include <shlobj.h>
  #include <shellapi.h>
#endif

namespace s2gp
{
    namespace
    {
        bool IsPdfPath(const char* p)
        {
            if (!p) return false;
            const size_t n = std::strlen(p);
            if (n < 4) return false;
            const auto eq = [](char a, char b) {
                return std::tolower(static_cast<unsigned char>(a)) == std::tolower(static_cast<unsigned char>(b));
            };
            return p[n-4] == '.'
                && eq(p[n-3], 'p') && eq(p[n-2], 'd') && eq(p[n-1], 'f');
        }

        bool FileExists(const char* path)
        {
            std::error_code ec;
            return std::filesystem::exists(path, ec);
        }

        // Byte-wise basename so CJK paths survive on Windows (std::filesystem
        // would round-trip through the ANSI codepage and mojibake them).
        std::string FilenameFromPath(const std::string& utf8Path)
        {
            const size_t cut = utf8Path.find_last_of("/\\");
            return (cut == std::string::npos) ? utf8Path
                                              : utf8Path.substr(cut + 1);
        }

        // Two-section pill, ported from pack-pdf's DrawFileTypeIcon.
        // Left dark slot (page number) is intentionally left blank in
        // score-pdf-to-gp since we work with one file at a time.
        void DrawFileTypePill(const char* typeLabel, ImU32 typeBg)
        {
            const float h         = ImGui::GetFrameHeight();
            const float numSecW   = ImGui::CalcTextSize("999").x + h * 0.4f;
            const float typeSecW  = ImGui::CalcTextSize("PNG").x + h * 0.6f;
            const float totalW    = numSecW + typeSecW;

            const ImVec2 pos = ImGui::GetCursorScreenPos();
            ImDrawList* dl   = ImGui::GetWindowDrawList();

            dl->AddRectFilled(pos, ImVec2(pos.x + totalW, pos.y + h), typeBg, h * 0.25f);
            dl->AddRectFilled(pos, ImVec2(pos.x + numSecW, pos.y + h), IM_COL32(0, 0, 0, 110), h * 0.25f, ImDrawFlags_RoundCornersLeft);

            const float typeX = pos.x + numSecW;
            const ImVec2 tts  = ImGui::CalcTextSize(typeLabel);
            dl->AddText(ImVec2(typeX + (typeSecW - tts.x) * 0.5f, pos.y + (h - tts.y) * 0.5f), IM_COL32_WHITE, typeLabel);

            ImGui::Dummy(ImVec2(totalW, h));
        }

        bool XButton(const char* str_id, ImVec2 size)
        {
            return Ui::IconButton(str_id, size, [](ImDrawList* dl, ImVec2 pos, ImVec2 sz, ImU32 /*frameBg*/)
            {
                const ImU32 fg    = ImGui::GetColorU32(ImGuiCol_Text);
                const float pad   = std::min(sz.x, sz.y) * 0.30f;
                const float thick = std::max(1.0f, ImGui::GetFontSize() * 0.12f);
                dl->AddLine(ImVec2(pos.x + pad, pos.y + pad), ImVec2(pos.x + sz.x - pad, pos.y + sz.y - pad), fg, thick);
                dl->AddLine(ImVec2(pos.x + sz.x - pad, pos.y + pad), ImVec2(pos.x + pad, pos.y + sz.y - pad), fg, thick);
            });
        }

        bool GearButton(const char* str_id, ImVec2 size)
        {
            return Ui::IconButton(str_id, size, [](ImDrawList* dl, ImVec2 pos, ImVec2 sz, ImU32 /*frameBg*/)
            {
                const ImU32 fg = ImGui::GetColorU32(ImGuiCol_Text);
                const ImVec2 c{ pos.x + sz.x * 0.5f, pos.y + sz.y * 0.5f };
                const float minDim = std::min(sz.x, sz.y);
                const float R       = minDim * 0.30f;
                const float r       = minDim * 0.10f;
                const float toothLen = minDim * 0.10f;
                const float thick    = std::max(1.5f, ImGui::GetFontSize() * 0.10f);
                const int   teeth    = 8;

                dl->AddCircle(c, R, fg, 24, thick);
                dl->AddCircle(c, r, fg, 12, thick);
                for (int i = 0; i < teeth; ++i)
                {
                    const float a = static_cast<float>(i) * 6.28318530718f / static_cast<float>(teeth);
                    const float ca = std::cos(a);
                    const float sa = std::sin(a);
                    const ImVec2 p1{ c.x + ca * R,                  c.y + sa * R };
                    const ImVec2 p2{ c.x + ca * (R + toothLen),     c.y + sa * (R + toothLen) };
                    dl->AddLine(p1, p2, fg, thick);
                }
            });
        }

#ifdef _WIN32
        std::wstring Utf8ToWide(const std::string& s)
        {
            if (s.empty()) return {};
            int n = MultiByteToWideChar(CP_UTF8, 0, s.data(), static_cast<int>(s.size()), nullptr, 0);
            std::wstring w(static_cast<size_t>(n), L'\0');
            MultiByteToWideChar(CP_UTF8, 0, s.data(), static_cast<int>(s.size()), w.data(), n);
            return w;
        }

        std::string WideToUtf8(const wchar_t* w)
        {
            if (!w || !*w) return {};
            int n = WideCharToMultiByte(CP_UTF8, 0, w, -1, nullptr, 0, nullptr, nullptr);
            if (n <= 1) return {};
            std::string s(static_cast<size_t>(n - 1), '\0');
            WideCharToMultiByte(CP_UTF8, 0, w, -1, s.data(), n - 1, nullptr, nullptr);
            return s;
        }

        std::filesystem::path ExeDir()
        {
            wchar_t buf[MAX_PATH];
            DWORD n = GetModuleFileNameW(nullptr, buf, MAX_PATH);
            if (n == 0 || n == MAX_PATH)
            {
                return std::filesystem::current_path();
            }
            return std::filesystem::path(std::wstring(buf, n)).parent_path();
        }

        std::filesystem::path ConfigPath()
        {
            return ExeDir() / L"userdata" / L"config.ini";
        }

        std::string DesktopPathUtf8()
        {
            PWSTR p = nullptr;
            if (SUCCEEDED(SHGetKnownFolderPath(FOLDERID_Desktop, 0, nullptr, &p)))
            {
                std::string r = WideToUtf8(p);
                CoTaskMemFree(p);
                return r;
            }
            return {};
        }

        std::string PickFolderDialog(const std::string& initialDirUtf8)
        {
            std::string result;
            HRESULT hrInit = CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED | COINIT_DISABLE_OLE1DDE);
            IFileOpenDialog* dlg = nullptr;
            if (SUCCEEDED(CoCreateInstance(CLSID_FileOpenDialog, nullptr, CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&dlg))))
            {
                DWORD opts = 0;
                dlg->GetOptions(&opts);
                dlg->SetOptions(opts | FOS_PICKFOLDERS | FOS_FORCEFILESYSTEM | FOS_PATHMUSTEXIST);

                if (!initialDirUtf8.empty())
                {
                    std::error_code ec;
                    if (std::filesystem::exists(initialDirUtf8, ec))
                    {
                        std::wstring wInit = Utf8ToWide(initialDirUtf8);
                        IShellItem* item = nullptr;
                        if (SUCCEEDED(SHCreateItemFromParsingName(wInit.c_str(), nullptr, IID_PPV_ARGS(&item))))
                        {
                            dlg->SetFolder(item);
                            item->Release();
                        }
                    }
                }

                if (SUCCEEDED(dlg->Show(nullptr)))
                {
                    IShellItem* item = nullptr;
                    if (SUCCEEDED(dlg->GetResult(&item)))
                    {
                        PWSTR path = nullptr;
                        if (SUCCEEDED(item->GetDisplayName(SIGDN_FILESYSPATH, &path)))
                        {
                            result = WideToUtf8(path);
                            CoTaskMemFree(path);
                        }
                        item->Release();
                    }
                }
                dlg->Release();
            }
            if (SUCCEEDED(hrInit))
            {
                CoUninitialize();
            }
            return result;
        }

        // PDF-only file picker. Initial directory falls back to the desktop
        // when the caller has nothing to suggest.
        std::string PickPdfDialog(const std::string& initialDirUtf8)
        {
            std::string result;
            HRESULT hrInit = CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED | COINIT_DISABLE_OLE1DDE);
            IFileOpenDialog* dlg = nullptr;
            if (SUCCEEDED(CoCreateInstance(CLSID_FileOpenDialog, nullptr, CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&dlg))))
            {
                DWORD opts = 0;
                dlg->GetOptions(&opts);
                dlg->SetOptions(opts | FOS_FORCEFILESYSTEM | FOS_FILEMUSTEXIST | FOS_PATHMUSTEXIST);

                COMDLG_FILTERSPEC filter[] = { { L"PDF documents", L"*.pdf" } };
                dlg->SetFileTypes(1, filter);
                dlg->SetFileTypeIndex(1);
                dlg->SetDefaultExtension(L"pdf");

                if (!initialDirUtf8.empty())
                {
                    std::error_code ec;
                    if (std::filesystem::exists(initialDirUtf8, ec))
                    {
                        std::wstring wInit = Utf8ToWide(initialDirUtf8);
                        IShellItem* item = nullptr;
                        if (SUCCEEDED(SHCreateItemFromParsingName(wInit.c_str(), nullptr, IID_PPV_ARGS(&item))))
                        {
                            dlg->SetFolder(item);
                            item->Release();
                        }
                    }
                }

                if (SUCCEEDED(dlg->Show(nullptr)))
                {
                    IShellItem* item = nullptr;
                    if (SUCCEEDED(dlg->GetResult(&item)))
                    {
                        PWSTR path = nullptr;
                        if (SUCCEEDED(item->GetDisplayName(SIGDN_FILESYSPATH, &path)))
                        {
                            result = WideToUtf8(path);
                            CoTaskMemFree(path);
                        }
                        item->Release();
                    }
                }
                dlg->Release();
            }
            if (SUCCEEDED(hrInit))
            {
                CoUninitialize();
            }
            return result;
        }

        // Open Explorer with the target file pre-selected. Used to land the
        // user inside the output folder on the freshly-written .gp.
        bool RevealInExplorer(const std::string& filePathUtf8)
        {
            std::wstring w = Utf8ToWide(filePathUtf8);
            // /select expects native Windows backslashes; convert in-place.
            for (wchar_t& c : w)
            {
                if (c == L'/') c = L'\\';
            }
            std::wstring params = L"/select,\"" + w + L"\"";
            HINSTANCE r = ShellExecuteW(nullptr, L"open", L"explorer.exe", params.c_str(), nullptr, SW_SHOWNORMAL);
            return reinterpret_cast<INT_PTR>(r) > 32;
        }
#else
        std::filesystem::path ConfigPath()
        {
            return std::filesystem::current_path() / "userdata" / "config.ini";
        }
        std::string DesktopPathUtf8() { return {}; }
        std::string PickFolderDialog(const std::string&) { return {}; }
        std::string PickPdfDialog(const std::string&)    { return {}; }
        bool RevealInExplorer(const std::string&)        { return false; }
#endif
    }

    void AppMainWindow::LoadFonts()
    {
        ImGuiIO& io = ImGui::GetIO();

        static ImVector<ImWchar> ranges;
        ranges.clear();

        ImFontGlyphRangesBuilder builder;
        builder.AddRanges(io.Fonts->GetGlyphRangesDefault());
        builder.AddRanges(io.Fonts->GetGlyphRangesChineseFull());
        builder.AddRanges(io.Fonts->GetGlyphRangesJapanese());
        builder.AddRanges(io.Fonts->GetGlyphRangesKorean());
        builder.AddRanges(io.Fonts->GetGlyphRangesCyrillic());
        builder.AddRanges(io.Fonts->GetGlyphRangesGreek());
        builder.AddRanges(io.Fonts->GetGlyphRangesThai());
        builder.AddRanges(io.Fonts->GetGlyphRangesVietnamese());
        builder.BuildRanges(&ranges);

        const float fontSize = 16.0f;

        const char* primaryPath = "C:/Windows/Fonts/msyh.ttc";
        ImFont* primary = nullptr;
        if (FileExists(primaryPath))
        {
            ImFontConfig cfg;
            cfg.OversampleH = 1;
            cfg.OversampleV = 1;
            cfg.PixelSnapH  = true;
            primary = io.Fonts->AddFontFromFileTTF(primaryPath, fontSize, &cfg, ranges.Data);
        }

        if (!primary)
        {
            io.Fonts->AddFontDefault();
            return;
        }

        const char* koreanPath = "C:/Windows/Fonts/malgun.ttf";
        if (FileExists(koreanPath))
        {
            ImFontConfig mergeCfg;
            mergeCfg.MergeMode  = true;
            mergeCfg.OversampleH = 1;
            mergeCfg.OversampleV = 1;
            mergeCfg.PixelSnapH  = true;
            io.Fonts->AddFontFromFileTTF(koreanPath, fontSize, &mergeCfg, ranges.Data);
        }
    }

    void AppMainWindow::ApplyImGuiStyle()
    {
        ImGuiStyle& style = ImGui::GetStyle();
        style.WindowRounding   = 4.0f;
        style.FrameRounding    = 3.0f;
        style.GrabRounding     = 3.0f;
        style.WindowPadding    = ImVec2(10, 10);
        style.FramePadding     = ImVec2(8, 4);
        style.ItemSpacing      = ImVec2(8, 6);

        ApplyTheme(m_Theme);
    }

    void AppMainWindow::OnFilesDropped(const char** paths, int count)
    {
        for (int i = 0; i < count; ++i)
        {
            if (IsPdfPath(paths[i]))
            {
                m_InputPath = paths[i];
                return;
            }
        }
    }

    AppMainWindow::AppMainWindow()
    {
        std::strncpy(m_OutputFile, "output.gp", sizeof(m_OutputFile) - 1);
        LoadConfig();
    }

    void AppMainWindow::LoadConfig()
    {
        bool gotFolder = false;

        const auto userPath    = ConfigPath();
        std::error_code ec;
        const bool fileExisted = std::filesystem::exists(userPath, ec);

        std::ifstream f(userPath);
        if (f)
        {
            std::string line;
            while (std::getline(f, line))
            {
                while (!line.empty() && (line.back() == '\r' || line.back() == '\n'))
                {
                    line.pop_back();
                }

                auto match = [&](const char* key) -> const char* {
                    const size_t klen = std::strlen(key);
                    if (line.size() >= klen && line.compare(0, klen, key) == 0)
                    {
                        return line.c_str() + klen;
                    }
                    return nullptr;
                };

                if (const char* val = match("folder="))
                {
                    if (*val != '\0')
                    {
                        std::strncpy(m_OutputDir, val, sizeof(m_OutputDir) - 1);
                        m_OutputDir[sizeof(m_OutputDir) - 1] = '\0';
                        gotFolder = true;
                    }
                }
                else if (const char* val = match("theme="))
                {
                    m_Theme = ThemeFromKey(val);
                }
                else if (const char* val = match("source_type="))
                {
                    if (std::strcmp(val, "tab") == 0)
                    {
                        m_SourceType = SourceType::Tab;
                    }
                    else
                    {
                        m_SourceType = SourceType::PianoSheet;
                    }
                }
            }
        }

        if (!gotFolder)
        {
            std::string desk = DesktopPathUtf8();
            if (desk.empty())
            {
                std::error_code fallbackEc;
                desk = std::filesystem::current_path(fallbackEc).generic_string();
            }
            std::strncpy(m_OutputDir, desk.c_str(), sizeof(m_OutputDir) - 1);
            m_OutputDir[sizeof(m_OutputDir) - 1] = '\0';
        }

        if (!fileExisted)
        {
            SaveConfig();
        }
    }

    void AppMainWindow::SaveConfig()
    {
        const std::filesystem::path cfg = ConfigPath();
        std::error_code ec;
        std::filesystem::create_directories(cfg.parent_path(), ec);

        std::ofstream f(cfg, std::ios::trunc);
        if (!f)
        {
            return;
        }
        f << "folder="      << m_OutputDir << '\n';
        f << "theme="       << ThemeKey(m_Theme) << '\n';
        f << "source_type=" << ((m_SourceType == SourceType::Tab) ? "tab" : "piano_sheet") << '\n';
    }

    void AppMainWindow::BrowseFolder()
    {
        std::string picked = PickFolderDialog(std::string(m_OutputDir));
        if (picked.empty())
        {
            return;
        }
        std::strncpy(m_OutputDir, picked.c_str(), sizeof(m_OutputDir) - 1);
        m_OutputDir[sizeof(m_OutputDir) - 1] = '\0';
        SaveConfig();
    }

    void AppMainWindow::PickInputFile()
    {
        std::string startDir;
        if (!m_InputPath.empty())
        {
            startDir = std::filesystem::path(m_InputPath).parent_path().generic_string();
        }
        if (startDir.empty())
        {
            startDir = m_OutputDir;
        }
        std::string picked = PickPdfDialog(startDir);
        if (picked.empty())
        {
            return;
        }
        m_InputPath = std::move(picked);
    }

    void AppMainWindow::ShowMessageDialog(std::string msg, std::string buttonLabel)
    {
        m_NoticeMessage   = std::move(msg);
        m_NoticeButton    = std::move(buttonLabel);
        m_NoticeRequested = true;
    }

    void AppMainWindow::Render()
    {
        ImGuiViewport* vp = ImGui::GetMainViewport();
        ImGui::SetNextWindowPos(vp->WorkPos);
        ImGui::SetNextWindowSize(vp->WorkSize);

        ImGuiWindowFlags flags = ImGuiWindowFlags_NoTitleBar
                               | ImGuiWindowFlags_NoResize
                               | ImGuiWindowFlags_NoMove
                               | ImGuiWindowFlags_NoCollapse
                               | ImGuiWindowFlags_NoBringToFrontOnFocus
                               | ImGuiWindowFlags_MenuBar;

        ImGui::Begin("score-pdf-to-gp", nullptr, flags);

        if (ImGui::BeginMenuBar())
        {
            if (ImGui::BeginMenu("Theme"))
            {
                for (int i = 0; i < kThemeCount; ++i)
                {
                    const bool selected = (m_Theme == kThemes[i].id);
                    if (ImGui::MenuItem(kThemes[i].displayName, nullptr, selected))
                    {
                        m_Theme = kThemes[i].id;
                        ApplyTheme(m_Theme);
                        SaveConfig();
                    }
                }
                ImGui::EndMenu();
            }
            ImGui::EndMenuBar();
        }

        ImGui::AlignTextToFramePadding();
        ImGui::TextDisabled("Drop a PDF onto this window, or click the path field to browse.");
        ImGui::Separator();

        // Footer = separator gap + "Output" label + 2 input rows + Dummy
        // breathing spacer + Convert button + extra breathing margin above
        // the window's bottom WindowPadding. Reserved here so the upper
        // child shrinks to the area above the bottom-anchored output panel.
        const ImGuiStyle& s = ImGui::GetStyle();
        const float footerH = s.ItemSpacing.y
                            + ImGui::GetTextLineHeightWithSpacing()
                            + ImGui::GetFrameHeightWithSpacing() * 2
                            + s.ItemSpacing.y * 4
                            + ImGui::GetFrameHeight();

        // Upper region soaks up whatever space is left above the bottom-
        // anchored output panel. Input row stays at the top with the natural
        // post-separator spacing — no extra vertical padding.
        ImGui::BeginChild("InputArea", ImVec2(0, -footerH), false);
        {
            RenderInputRow();
        }
        ImGui::EndChild();

        RenderOutputPanel();
        RenderPianoParamsPopup();
        RenderNoticePopup();

        ImGui::End();
    }

    void AppMainWindow::RenderInputRow()
    {
        const ImGuiStyle& s = ImGui::GetStyle();
        const float rowH    = ImGui::GetFrameHeight();
        const float spacing = s.ItemSpacing.x;
        const float btnW    = rowH;

        // Right-side reserved column: optional gear (Piano only) + clear-X.
        // Both slots are always reserved so the path column width is stable
        // when the source type or input state toggles.
        const float trailingW = btnW * 2 + spacing * 2;

        ImGui::PushID("input");

        DrawFileTypePill("PDF", IM_COL32(196, 64, 64, 255));
        ImGui::SameLine();

        const float dropdownW = UiSize::RowDropdownWidth();
        ImGui::SetNextItemWidth(dropdownW);
        const char* items[] = { "Piano Sheet", "Tab" };
        int cur = static_cast<int>(m_SourceType);
        if (ImGui::Combo("##sourcetype", &cur, items, IM_ARRAYSIZE(items)))
        {
            m_SourceType = static_cast<SourceType>(cur);
            SaveConfig();
        }
        ImGui::SameLine();

        // Path slot: filename + tooltip with full path. Click to browse.
        const float availW   = std::max(1.0f, ImGui::GetContentRegionAvail().x - trailingW);
        const std::string filename = m_InputPath.empty()
            ? std::string("(Click to browse, or drop a PDF here)")
            : FilenameFromPath(m_InputPath);

        ImGui::PushStyleVar(ImGuiStyleVar_SelectableTextAlign, ImVec2(0.0f, 0.5f));
        if (ImGui::Selectable(filename.c_str(), false, 0, ImVec2(availW, rowH)))
        {
            PickInputFile();
        }
        ImGui::PopStyleVar();

        if (!m_InputPath.empty() && ImGui::IsItemHovered())
        {
            ImGui::SetTooltip("%s", m_InputPath.c_str());
        }

        // Right-anchored trailing column.
        ImGui::SameLine();
        Ui::RightAlignCursorX(trailingW - spacing);

        if (m_SourceType == SourceType::PianoSheet)
        {
            if (GearButton("##gear", ImVec2(btnW, rowH)))
            {
                m_PianoParamsRequested = true;
            }
            if (ImGui::IsItemHovered())
            {
                ImGui::SetTooltip("Piano sheet parameters");
            }
        }
        else
        {
            ImGui::Dummy(ImVec2(btnW, rowH));
        }
        ImGui::SameLine();

        if (!m_InputPath.empty())
        {
            if (XButton("##clear", ImVec2(btnW, rowH)))
            {
                m_InputPath.clear();
            }
        }
        else
        {
            ImGui::Dummy(ImVec2(btnW, rowH));
        }

        ImGui::PopID();
    }

    void AppMainWindow::RenderOutputPanel()
    {
        const ImGuiStyle& s = ImGui::GetStyle();

        ImGui::Separator();
        ImGui::TextDisabled("Output");

        const float labelW = ImGui::CalcTextSize("Filename").x + s.ItemSpacing.x * 2;
        const float trailW = UiSize::InterfaceButtonSmall.x + s.ItemSpacing.x;

        ImGui::AlignTextToFramePadding();
        ImGui::TextUnformatted("Folder");
        ImGui::SameLine(labelW);
        ImGui::SetNextItemWidth(-trailW);
        if (ImGui::InputText("##outdir", m_OutputDir, sizeof(m_OutputDir)))
        {
            SaveConfig();
        }
        ImGui::SameLine();
        if (ImGui::Button("Browse", UiSize::InterfaceButtonSmall))
        {
            BrowseFolder();
        }

        ImGui::AlignTextToFramePadding();
        ImGui::TextUnformatted("Filename");
        ImGui::SameLine(labelW);
        ImGui::SetNextItemWidth(-FLT_MIN);
        ImGui::InputText("##outfile", m_OutputFile, sizeof(m_OutputFile));

        // Breathing space between Filename and Convert so the button does not
        // glue to the bottom edge once WindowPadding closes the frame below.
        ImGui::Dummy(ImVec2(0.0f, s.ItemSpacing.y));

        Ui::CenterCursorX(UiSize::InterfaceButtonMedium.x);
        if (ImGui::Button("Convert", UiSize::InterfaceButtonMedium))
        {
            Convert();
        }
    }

    void AppMainWindow::RenderPianoParamsPopup()
    {
        const char* id = "Piano Sheet Parameters##s2gp";
        if (m_PianoParamsRequested)
        {
            ImGui::OpenPopup(id);
            m_PianoParamsRequested = false;
        }

        ImVec2 center = ImGui::GetMainViewport()->GetCenter();
        ImGui::SetNextWindowPos(center, ImGuiCond_Appearing, ImVec2(0.5f, 0.5f));
        ImGui::SetNextWindowSize(ImVec2(420.0f, 0.0f), ImGuiCond_Appearing);

        if (ImGui::BeginPopupModal(id, nullptr, ImGuiWindowFlags_NoSavedSettings))
        {
            ImGui::TextDisabled("Voice budget, melody channel, bass floor, octave fold,");
            ImGui::TextDisabled("chord mode, tuning. Wired up in Phase 3.");
            ImGui::Dummy(ImVec2(0, ImGui::GetStyle().ItemSpacing.y));

            const float btnW = UiSize::DialogButton.x;
            Ui::CenterCursorX(btnW);
            if (ImGui::Button("Close", UiSize::DialogButton)
                || ImGui::IsKeyPressed(ImGuiKey_Enter)
                || ImGui::IsKeyPressed(ImGuiKey_Escape))
            {
                ImGui::CloseCurrentPopup();
            }
            ImGui::EndPopup();
        }
    }

    void AppMainWindow::RenderNoticePopup()
    {
        const char* id = "Notice##s2gp";
        if (m_NoticeRequested)
        {
            ImGui::OpenPopup(id);
            m_NoticeRequested = false;
        }

        const ImGuiStyle& s = ImGui::GetStyle();
        const float btnW     = UiSize::DialogButton.x;
        const float textW    = ImGui::CalcTextSize(m_NoticeMessage.c_str()).x;
        const float contentW = std::max(textW, btnW);
        const float popupW   = contentW + s.WindowPadding.x * 2.0f;

        ImVec2 center = ImGui::GetMainViewport()->GetCenter();
        ImGui::SetNextWindowPos(center, ImGuiCond_Appearing, ImVec2(0.5f, 0.5f));
        ImGui::SetNextWindowSize(ImVec2(popupW, 0.0f));

        if (ImGui::BeginPopupModal(id, nullptr, ImGuiWindowFlags_NoSavedSettings))
        {
            Ui::CenterCursorX(textW);
            ImGui::TextUnformatted(m_NoticeMessage.c_str());
            ImGui::Dummy(ImVec2(0, s.ItemSpacing.y));

            Ui::CenterCursorX(btnW);
            if (ImGui::Button(m_NoticeButton.c_str(), UiSize::DialogButton)
                || ImGui::IsKeyPressed(ImGuiKey_Enter)
                || ImGui::IsKeyPressed(ImGuiKey_Escape))
            {
                ImGui::CloseCurrentPopup();
            }
            ImGui::EndPopup();
        }
    }

    void AppMainWindow::Convert()
    {
        if (m_InputPath.empty())
        {
            ShowMessageDialog("Drop a PDF first.");
            return;
        }
        std::string dir(m_OutputDir);
        std::string file(m_OutputFile);
        if (dir.empty() || file.empty())
        {
            ShowMessageDialog("Folder and filename are required.");
            return;
        }
        ShowMessageDialog("Convert pipeline (oemer + GPIF emit) is not implemented yet — Phase 2 / 4 work in progress.");
    }
}
