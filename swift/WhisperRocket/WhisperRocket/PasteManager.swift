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
            // 4. Cmd+V szimuláció
            self.simulatePaste()
        }
    }

    /// Cmd+V billentyű szimuláció (macOS-en mindenhol Cmd+V működik)
    private func simulatePaste() {
        let source = CGEventSource(stateID: .hidSystemState)

        // V key = 0x09
        let keyDown = CGEvent(keyboardEventSource: source, virtualKey: 0x09, keyDown: true)
        let keyUp = CGEvent(keyboardEventSource: source, virtualKey: 0x09, keyDown: false)

        // Cmd+V flag
        keyDown?.flags = .maskCommand
        keyUp?.flags = .maskCommand

        // Post events
        keyDown?.post(tap: .cghidEventTap)
        keyUp?.post(tap: .cghidEventTap)

        print("PasteManager: Cmd+V simulated")
    }
}
