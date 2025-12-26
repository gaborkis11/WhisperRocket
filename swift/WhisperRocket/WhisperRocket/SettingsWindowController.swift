//
//  SettingsWindowController.swift
//  WhisperRocket
//
//  Created by Gabor Kis on 2025. 12. 26..
//

import Cocoa
import SwiftUI

/// Settings ablak kezelő
class SettingsWindowController {
    static let shared = SettingsWindowController()

    private var window: NSWindow?

    private init() {}

    /// Settings ablak megnyitása
    func showSettings() {
        // Ha már van ablak, hozzuk előtérbe
        if let existingWindow = window {
            existingWindow.makeKeyAndOrderFront(nil)
            NSApp.activate(ignoringOtherApps: true)
            return
        }

        // Új ablak létrehozása
        let settingsView = SettingsView()
        let hostingController = NSHostingController(rootView: settingsView)

        let newWindow = NSWindow(contentViewController: hostingController)
        newWindow.title = "WhisperRocket Settings"
        newWindow.styleMask = [.titled, .closable, .miniaturizable]
        newWindow.setContentSize(NSSize(width: 580, height: 530))
        newWindow.center()

        // Ablak bezárásakor nullázzuk a referenciát
        newWindow.isReleasedWhenClosed = false
        newWindow.delegate = WindowDelegate.shared

        self.window = newWindow

        // Megjelenítés és előtérbe hozás
        newWindow.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    /// Ablak bezárása
    func closeSettings() {
        window?.close()
        window = nil
    }

    /// Ablak referencia törlése (delegate hívja)
    func windowWillClose() {
        window = nil
    }
}

/// Window delegate az ablak bezárás kezeléséhez
class WindowDelegate: NSObject, NSWindowDelegate {
    static let shared = WindowDelegate()

    func windowWillClose(_ notification: Notification) {
        SettingsWindowController.shared.windowWillClose()
    }
}
