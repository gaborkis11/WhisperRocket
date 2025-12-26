//
//  PasteManager.swift
//  WhisperRocket
//
//  Created by Gabor Kis on 2025. 12. 26..
//

import Cocoa
import Carbon

/// Auto-paste kezelő - clipboard és billentyű szimuláció
class PasteManager {
    static let shared = PasteManager()

    /// Terminál alkalmazások bundle ID-k (Cmd+Shift+V kell nekik)
    private let terminalBundles = [
        "com.apple.Terminal",
        "com.googlecode.iterm2",
        "io.alacritty",
        "dev.warp.Warp-Stable",
        "com.microsoft.VSCode",
        "com.todesktop.230313mzl4w4u92"  // Cursor
    ]

    private init() {}

    /// Szöveg beillesztése az aktív alkalmazásba
    func pasteText(_ text: String) {
        // 1. Clipboard-ra másolás (mindig megtörténik)
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(text, forType: .string)
        print("PasteManager: Text copied to clipboard")

        // 2. Ellenőrizzük az Accessibility engedélyt a paste szimulációhoz
        if !HotkeyManager.checkAccessibilityPermission() {
            print("PasteManager: No Accessibility permission - text is on clipboard, use Cmd+V manually")
            return
        }

        // 3. Kis késleltetés, hogy a clipboard frissüljön
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
            // 4. Cmd+V (vagy Cmd+Shift+V terminálnál) szimuláció
            self.simulatePaste()
        }
    }

    /// Cmd+V billentyű szimuláció
    private func simulatePaste() {
        let source = CGEventSource(stateID: .hidSystemState)

        // V key = 0x09
        let keyDown = CGEvent(keyboardEventSource: source, virtualKey: 0x09, keyDown: true)
        let keyUp = CGEvent(keyboardEventSource: source, virtualKey: 0x09, keyDown: false)

        // Cmd flag hozzáadása (terminálnál Cmd+Shift)
        if isTerminalApp() {
            keyDown?.flags = [.maskCommand, .maskShift]
            keyUp?.flags = [.maskCommand, .maskShift]
            print("PasteManager: Using Cmd+Shift+V for terminal app")
        } else {
            keyDown?.flags = .maskCommand
            keyUp?.flags = .maskCommand
            print("PasteManager: Using Cmd+V")
        }

        // Post events
        keyDown?.post(tap: .cghidEventTap)
        keyUp?.post(tap: .cghidEventTap)

        print("PasteManager: Paste simulated")
    }

    /// Ellenőrzi, hogy terminál app-e az aktív alkalmazás
    func isTerminalApp() -> Bool {
        guard let app = NSWorkspace.shared.frontmostApplication else { return false }
        let bundleId = app.bundleIdentifier ?? ""
        let isTerminal = terminalBundles.contains(bundleId)
        if isTerminal {
            print("PasteManager: Detected terminal app: \(bundleId)")
        }
        return isTerminal
    }
}
