//
//  AppDelegate.swift
//  WhisperRocket
//
//  Created by Gabor Kis on 2025. 12. 26..
//

import Cocoa
import SwiftUI
import Combine

class AppDelegate: NSObject, NSApplicationDelegate {

    func applicationDidFinishLaunching(_ notification: Notification) {
        print("WhisperRocket started")

        // ModelManager inicializálása AZONNAL - hogy a modell betöltése elinduljon
        // (lazy singleton, ezért explicit hozzáférés kell)
        _ = ModelManager.shared
        print("ModelManager initialized")

        // Accessibility engedély ellenőrzése (hotkey + auto-paste)
        if !HotkeyManager.checkAccessibilityPermission() {
            print("WARNING: Accessibility permission not granted")
            // Rendszer dialógus megnyitása - automatikusan hozzáadja az appot a listához
            HotkeyManager.requestAccessibilityPermission()
        }

        // Mikrofon engedély ellenőrzése
        if !AudioRecorder.shared.hasPermission {
            print("WARNING: Microphone permission not granted")
            // A permission kérés automatikusan megtörténik az AudioRecorder init-ben
        }

        // Hotkey callback beállítása - AppState-et használjuk
        HotkeyManager.shared.onHotkeyPressed = {
            AppState.shared.toggleRecording()
        }

        // Hotkey listener indítása
        HotkeyManager.shared.startListening()

        // Popup ablak inicializálása
        _ = PopupWindowController.shared
        print("PopupWindowController initialized")
    }

    func applicationWillTerminate(_ notification: Notification) {
        print("WhisperRocket terminating")

        // Hotkey listener leállítása
        HotkeyManager.shared.stopListening()
    }

    /// Engedély dialógus megjelenítése
    private func showPermissionAlert() {
        DispatchQueue.main.async {
            let alert = NSAlert()
            alert.messageText = "Accessibility Permission Required"
            alert.informativeText = "WhisperRocket needs Accessibility permission for:\n\n• Global hotkey detection (Ctrl+Shift+S)\n• Auto-paste transcribed text\n\nPlease enable it in System Settings → Privacy & Security → Accessibility."
            alert.alertStyle = .warning
            alert.addButton(withTitle: "Open Settings")
            alert.addButton(withTitle: "Later")

            NSApp.activate(ignoringOtherApps: true)

            let response = alert.runModal()
            if response == .alertFirstButtonReturn {
                HotkeyManager.openAccessibilitySettings()
            }
        }
    }
}
