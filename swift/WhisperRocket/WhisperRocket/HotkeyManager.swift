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

    // KeyCode mapping (karakter -> Carbon keyCode)
    private let keyCodeMap: [String: UInt32] = [
        "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7,
        "c": 8, "v": 9, "b": 11, "q": 12, "w": 13, "e": 14, "r": 15,
        "y": 16, "t": 17, "1": 18, "2": 19, "3": 20, "4": 21, "6": 22,
        "5": 23, "=": 24, "9": 25, "7": 26, "-": 27, "8": 28, "0": 29,
        "]": 30, "o": 31, "u": 32, "[": 33, "i": 34, "p": 35, "l": 37,
        "j": 38, "'": 39, "k": 40, ";": 41, "\\": 42, ",": 43, "/": 44,
        "n": 45, "m": 46, ".": 47, "`": 50, " ": 49
    ]

    private init() {}

    /// Aktuális hotkey beolvasása UserDefaults-ból
    private var currentHotkey: String {
        UserDefaults.standard.string(forKey: "hotkey") ?? "ctrl+shift+s"
    }

    /// Hotkey string parsing -> (keyCode, modifiers)
    private func parseHotkey(_ hotkey: String) -> (keyCode: UInt32, modifiers: UInt32)? {
        let parts = hotkey.lowercased().split(separator: "+").map { String($0) }

        guard parts.count >= 2 else { return nil }

        // Modifiers
        var modifiers: UInt32 = 0
        for part in parts.dropLast() {
            switch part {
            case "ctrl", "control":
                modifiers |= UInt32(controlKey)
            case "shift":
                modifiers |= UInt32(shiftKey)
            case "alt", "option":
                modifiers |= UInt32(optionKey)
            case "cmd", "command":
                modifiers |= UInt32(cmdKey)
            default:
                break
            }
        }

        // KeyCode
        guard let lastPart = parts.last,
              let keyCode = keyCodeMap[lastPart] else {
            return nil
        }

        return (keyCode, modifiers)
    }

    /// Hotkey listener indítása
    func startListening() {
        guard hotKeyRef == nil else {
            print("HotkeyManager: Already listening")
            return
        }

        // Hotkey parsing
        let hotkey = currentHotkey
        guard let (keyCode, modifiers) = parseHotkey(hotkey) else {
            print("HotkeyManager: Invalid hotkey format: \(hotkey)")
            return
        }

        print("HotkeyManager: Registering keyCode=\(keyCode), modifiers=\(modifiers) for '\(hotkey)'")

        // Event handler beállítása
        var eventType = EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed))

        let status = InstallEventHandler(
            GetApplicationEventTarget(),
            { (nextHandler, event, userData) -> OSStatus in
                // Callback hívása
                if let userData = userData {
                    let hotkeyManager = Unmanaged<HotkeyManager>.fromOpaque(userData).takeUnretainedValue()
                    print("HotkeyManager: ✅ Hotkey detected! (\(hotkeyManager.currentHotkey))")
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
        print("HotkeyManager: Started listening for \(hotkey) (Carbon)")
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
