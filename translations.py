#!/usr/bin/env python3
"""
WhisperRocket - Többnyelvű UI támogatás
Angol alapértelmezett, magyar választható
"""

TRANSLATIONS = {
    "en": {
        # System tray
        "tray_settings": "Settings",
        "tray_about": "About",
        "tray_quit": "Quit",
        "tray_loading": "WhisperRocket - Loading...",
        "tray_ready": "WhisperRocket - Ready",
        "tray_recording": "WhisperRocket - RECORDING",
        "tray_processing": "WhisperRocket - Processing...",
        "tray_done": "WhisperRocket - Done! Ctrl+V",
        "tray_error": "WhisperRocket - ERROR!",

        # Popup
        "popup_recording": "Recording",
        "popup_done": "Done",
        "popup_finish": "Finish",
        "popup_cancel": "Cancel",
        "popup_expand": "Click to expand",
        "popup_copy": "Copy",

        # Settings - general
        "settings_title": "WhisperRocket Settings",
        "tab_settings": "Settings",
        "tab_models": "Models",
        "label_ui_language": "UI Language:",
        "label_language": "Language:",
        "label_hotkey": "Hotkey:",
        "label_model": "Model:",
        "label_device": "Device:",
        "label_popup_duration": "Popup duration:",
        "suffix_seconds": " sec",
        "btn_record": "Record",
        "btn_save": "Save",
        "btn_save_restart": "Save and restart",
        "btn_cancel": "Cancel",
        "autostart": "Start on system boot",
        "info_restart": "Note: Model/UI language changes require restart.",

        # Settings - models tab
        "models_downloaded": "Downloaded models:",
        "storage_info": "Total: {total} | Freeable: {free}",
        "info_active_model": "Active model cannot be deleted.",
        "btn_refresh": "Refresh",
        "btn_delete_selected": "Delete selected",
        "btn_delete_all": "Delete all unused",
        "btn_close": "Close",

        # Dialogs
        "dlg_warning": "Warning",
        "dlg_confirm": "Confirm",
        "dlg_success": "Success",
        "dlg_error": "Error",
        "dlg_info": "Info",
        "dlg_saved": "Saved",
        "dlg_select_model": "Select a model to delete!",
        "dlg_active_no_delete": "Active model cannot be deleted!",
        "dlg_confirm_delete": "Delete {model}?",
        "dlg_confirm_delete_all": "Delete all unused models?\n\nFreeable space: {size}",
        "dlg_deleted": "{count} model(s) deleted!\nFreed space: {size}",
        "dlg_no_deletable": "No models to delete!",
        "dlg_download": "Download Model",
        "dlg_download_ask": "{model} is not downloaded.\n\nDownload now?",
        "dlg_settings_saved": "Settings saved!\n\nChanges take effect after restart.",
        "dlg_download_in_progress": "A download is in progress.\n\nCancel and switch to new model?",
        "dlg_model_deleted": "Model {model} deleted!",
        "dlg_model_not_found": "Model not found.",
        "dlg_delete_error": "Delete error: {error}",

        # Download
        "download_title": "Downloading: {model}",
        "download_starting": "Starting...",
        "download_done": "Downloaded: {model}",
        "download_complete": "Download complete!",
        "download_error": "Error: {model}",
        "download_cancelled": "Download cancelled",
        "download_stall": "Downloading... (writing large file)",

        # Hotkey
        "hotkey_press": "Press key combination...",

        # History
        "tray_history": "History",
        "history_clear": "Clear History",
        "history_entries": "{count} entries ({size})",
        "history_empty": "No history yet",
        "history_copy": "Copy",
        "history_copied": "Copied!",
        "history_confirm_clear": "Delete all history entries?",
        "history_cleared": "History cleared!",

        # Setup Wizard
        "wizard_title": "WhisperRocket Setup",
        "wizard_welcome": "Welcome to WhisperRocket!",
        "wizard_select_model": "Please select a model to get started:",
        "wizard_model_tiny": "Tiny (~75 MB) - Fastest, lower accuracy",
        "wizard_model_base": "Base (~150 MB) - Fast, basic accuracy",
        "wizard_model_small": "Small (~500 MB) - Balanced (Recommended)",
        "wizard_model_medium": "Medium (~1.5 GB) - Good accuracy",
        "wizard_model_large": "Large-v3 (~3 GB) - Best accuracy",
        "wizard_model_turbo": "Large-v3-turbo (~1.6 GB) - Fast & accurate",
        "wizard_download_start": "Download & Start",
        "wizard_downloading": "Downloading...",
        "wizard_progress": "{downloaded} / {total}",

        # Permission Section (Settings)
        "perm_title": "Permissions Required",
        "perm_description": "Hotkey capture requires Input Monitoring permission.",
        "perm_status_granted": "Status: Granted",
        "perm_status_not_granted": "Status: Not granted",
        "perm_open_settings": "Open System Settings",
        "perm_restart_note": "After enabling, restart the app.",

        # Model Warning (Settings)
        "model_warning_title": "Model Not Downloaded",
        "model_warning_text": "The selected model \"{model}\" is not downloaded. The app won't work until you download a model.",
        "model_warning_download": "Download Now",
    },
    "hu": {
        # System tray
        "tray_settings": "Beállítások",
        "tray_about": "Névjegy",
        "tray_quit": "Kilépés",
        "tray_loading": "WhisperRocket - Betöltés...",
        "tray_ready": "WhisperRocket - Készen áll",
        "tray_recording": "WhisperRocket - FELVÉTEL",
        "tray_processing": "WhisperRocket - Feldolgozás...",
        "tray_done": "WhisperRocket - Kész! Ctrl+V",
        "tray_error": "WhisperRocket - HIBA!",

        # Popup
        "popup_recording": "Felvétel",
        "popup_done": "Kész",
        "popup_finish": "Befejez",
        "popup_cancel": "Mégse",
        "popup_expand": "Kattints a kibontáshoz",
        "popup_copy": "Másolás",

        # Settings - general
        "settings_title": "WhisperRocket Beállítások",
        "tab_settings": "Beállítások",
        "tab_models": "Modellek",
        "label_ui_language": "UI Nyelv:",
        "label_language": "Nyelv:",
        "label_hotkey": "Hotkey:",
        "label_model": "Modell:",
        "label_device": "Eszköz:",
        "label_popup_duration": "Popup időtartam:",
        "suffix_seconds": " mp",
        "btn_record": "Rögzít",
        "btn_save": "Mentés",
        "btn_save_restart": "Mentés és újraindítás",
        "btn_cancel": "Mégse",
        "autostart": "Indítás rendszerindításkor",
        "info_restart": "Megjegyzés: Modell/UI nyelv váltás újraindítást igényel.",

        # Settings - models tab
        "models_downloaded": "Letöltött modellek:",
        "storage_info": "Összesen: {total} | Felszabadítható: {free}",
        "info_active_model": "Az aktív modell nem törölhető.",
        "btn_refresh": "Frissítés",
        "btn_delete_selected": "Kijelölt törlése",
        "btn_delete_all": "Összes nem használt törlése",
        "btn_close": "Bezár",

        # Dialogs
        "dlg_warning": "Figyelmeztetés",
        "dlg_confirm": "Megerősítés",
        "dlg_success": "Siker",
        "dlg_error": "Hiba",
        "dlg_info": "Info",
        "dlg_saved": "Mentve",
        "dlg_select_model": "Válassz ki egy modellt a törléshez!",
        "dlg_active_no_delete": "Az aktív modell nem törölhető!",
        "dlg_confirm_delete": "Törlöd a(z) {model} modellt?",
        "dlg_confirm_delete_all": "Törlöd az összes nem használt modellt?\n\nFelszabaduló tárhely: {size}",
        "dlg_deleted": "{count} modell törölve!\nFelszabadított tárhely: {size}",
        "dlg_no_deletable": "Nincs törölhető modell!",
        "dlg_download": "Modell letöltése",
        "dlg_download_ask": "A(z) {model} modell nincs letöltve.\n\nLetöltöd most?",
        "dlg_settings_saved": "Beállítások elmentve!\n\nA változások újraindítás után lépnek érvénybe.",
        "dlg_download_in_progress": "Letöltés folyamatban.\n\nMegszakítod és váltasz az új modellre?",
        "dlg_model_deleted": "A(z) {model} modell törölve!",
        "dlg_model_not_found": "A modell nem található.",
        "dlg_delete_error": "Törlési hiba: {error}",

        # Download
        "download_title": "Letöltés: {model}",
        "download_starting": "Indítás...",
        "download_done": "Letöltve: {model}",
        "download_complete": "Letöltés kész!",
        "download_error": "Hiba: {model}",
        "download_cancelled": "Letöltés megszakítva",
        "download_stall": "Letöltés... (nagy fájl írása)",

        # Hotkey
        "hotkey_press": "Nyomd meg a billentyűkombinációt...",

        # History
        "tray_history": "Előzmények",
        "history_clear": "Előzmények törlése",
        "history_entries": "{count} bejegyzés ({size})",
        "history_empty": "Még nincs előzmény",
        "history_copy": "Másolás",
        "history_copied": "Másolva!",
        "history_confirm_clear": "Törlöd az összes előzményt?",
        "history_cleared": "Előzmények törölve!",

        # Setup Wizard
        "wizard_title": "WhisperRocket Beállítás",
        "wizard_welcome": "Üdvözöl a WhisperRocket!",
        "wizard_select_model": "Válassz egy modellt a kezdéshez:",
        "wizard_model_tiny": "Tiny (~75 MB) - Leggyorsabb, alacsony pontosság",
        "wizard_model_base": "Base (~150 MB) - Gyors, alap pontosság",
        "wizard_model_small": "Small (~500 MB) - Kiegyensúlyozott (Ajánlott)",
        "wizard_model_medium": "Medium (~1.5 GB) - Jó pontosság",
        "wizard_model_large": "Large-v3 (~3 GB) - Legjobb pontosság",
        "wizard_model_turbo": "Large-v3-turbo (~1.6 GB) - Gyors és pontos",
        "wizard_download_start": "Letöltés és indítás",
        "wizard_downloading": "Letöltés...",
        "wizard_progress": "{downloaded} / {total}",

        # Permission Section (Settings)
        "perm_title": "Engedélyek szükségesek",
        "perm_description": "A gyorsbillentyű működéséhez Input Monitoring engedély szükséges.",
        "perm_status_granted": "Állapot: Engedélyezve",
        "perm_status_not_granted": "Állapot: Nincs megadva",
        "perm_open_settings": "Rendszerbeállítások megnyitása",
        "perm_restart_note": "Engedélyezés után indítsd újra az alkalmazást.",

        # Model Warning (Settings)
        "model_warning_title": "Modell nincs letöltve",
        "model_warning_text": "A kiválasztott \"{model}\" modell nincs letöltve. Az alkalmazás nem működik modell nélkül.",
        "model_warning_download": "Letöltés most",
    }
}


def t(key: str, lang: str = "en", **kwargs) -> str:
    """
    Fordítás lekérése.

    Használat:
        t("tray_ready", "hu")
        t("dlg_confirm_delete", "en", model="large-v3")
    """
    text = TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass  # Ha hiányzik paraméter, eredeti szöveg marad
    return text
