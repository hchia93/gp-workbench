#pragma once

namespace s2gp
{
    enum class ThemeId : int
    {
        PhotoshopDark = 0, // neutral graphite, zero color cast
        Walnut,            // warm dark brown + amber accents
        Monokai,           // warm grey + vivid orange/pink/yellow
        ImGuiDark,         // baseline fallback
    };

    struct ThemeInfo
    {
        ThemeId     id;
        const char* displayName; // shown in the Theme menu
        const char* configKey;   // serialized into config.ini
    };

    extern const ThemeInfo kThemes[];
    extern const int       kThemeCount;

    // Resets to dark baseline then overrides per-theme slots.
    void ApplyTheme(ThemeId id);

    // Unknown / legacy keys fall back to kThemes[0].id (PhotoshopDark).
    ThemeId     ThemeFromKey(const char* key);
    const char* ThemeKey(ThemeId id);
}
