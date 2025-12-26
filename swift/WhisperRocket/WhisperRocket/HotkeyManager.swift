//
//  HotkeyManager.swift
//  WhisperRocket
//
//  Created by Gabor Kis on 2025. 12. 26..
//

import Cocoa
import Carbon
import Combine

/// Globális hotkey kezelő - Carbon RegisterEventHotKey alapú implementáció
class HotkeyManager: ObservableObject {
    static let shared = HotkeyManager()

    // Hotkey callback
    var onHotkeyPressed: (() -> Void)?

    // Állapot
    @Published var isListening = false

    // Carbon hotkey
    private var hotKeyRef: EventHotKeyRef?
    private var eventHandler: EventHandlerRef?

    // Hotkey konfiguráció: Ctrl+Shift+S
    // S = keycode 1, Ctrl = controlKey, Shift = shiftKey
    private let keyCode: UInt32 = 1  // 'S' key
    private let modifiers: UInt32 = UInt32(controlKey | shiftKey)

    private init() {}

    /// Hotkey listener indítása
    func startListening() {
        guard hotKeyRef == nil else {
            print("HotkeyManager: Already listening")
            return
        }

        // Event handler beállítása
        var eventType = EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed))

        let status = InstallEventHandler(
            GetApplicationEventTarget(),
            { (nextHandler, event, userData) -> OSStatus in
                // Callback hívása
                if let userData = userData {
                    let hotkeyManager = Unmanaged<HotkeyManager>.fromOpaque(userData).takeUnretainedValue()
                    print("HotkeyManager: ✅ Hotkey detected! (Ctrl+Shift+S)")
                    DispatchQueue.main.async {
                        hotkeyManager.onHotkeyPressed?()
                    }
                }
                return noErr
            },
            1,
            &eventType,
            Unmanaged.passUnretained(self).toOpaque(),
            &eventHandler
        )

        guard status == noErr else {
            print("HotkeyManager: Failed to install event handler, status: \(status)")
            return
        }

        // Hotkey regisztrálása
        let hotKeyID = EventHotKeyID(signature: OSType(0x57525B54), id: 1) // "WR[T" signature
        let registerStatus = RegisterEventHotKey(
            keyCode,
            modifiers,
            hotKeyID,
            GetApplicationEventTarget(),
            0,
            &hotKeyRef
        )

        guard registerStatus == noErr else {
            print("HotkeyManager: Failed to register hotkey, status: \(registerStatus)")
            return
        }

        isListening = true
        print("HotkeyManager: Started listening for Ctrl+Shift+S (Carbon)")
    }

    /// Hotkey listener leállítása
    func stopListening() {
        if let hotKeyRef = hotKeyRef {
            UnregisterEventHotKey(hotKeyRef)
            self.hotKeyRef = nil
        }

        if let eventHandler = eventHandler {
            RemoveEventHandler(eventHandler)
            self.eventHandler = nil
        }

        isListening = false
        print("HotkeyManager: Stopped listening")
    }

    /// Accessibility engedély ellenőrzése (hotkey + auto-paste-hez kell)
    static func checkAccessibilityPermission() -> Bool {
        // Először ellenőrizzük prompt nélkül
        let checkOptions = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: false]
        return AXIsProcessTrustedWithOptions(checkOptions as CFDictionary)
    }

    /// Accessibility engedély kérése (megnyitja a rendszer dialógust)
    static func requestAccessibilityPermission() {
        let promptOptions = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true]
        AXIsProcessTrustedWithOptions(promptOptions as CFDictionary)
    }

    /// Accessibility beállítások megnyitása
    static func openAccessibilitySettings() {
        if let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility") {
            NSWorkspace.shared.open(url)
        }
    }
}
