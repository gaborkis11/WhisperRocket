//
//  LaunchAtLoginManager.swift
//  WhisperRocket
//
//  Created by Gabor Kis on 2025. 12. 27..
//

import ServiceManagement
import Foundation

/// Launch at Login kezelő - SMAppService alapú (macOS 13+)
struct LaunchAtLoginManager {

    /// Ellenőrzi, hogy be van-e kapcsolva az automatikus indítás
    static var isEnabled: Bool {
        get {
            if #available(macOS 13.0, *) {
                return SMAppService.mainApp.status == .enabled
            } else {
                // Fallback régebbi macOS-re
                return UserDefaults.standard.bool(forKey: "launchAtLogin")
            }
        }
        set {
            if #available(macOS 13.0, *) {
                do {
                    if newValue {
                        try SMAppService.mainApp.register()
                        print("LaunchAtLogin: Enabled")
                    } else {
                        try SMAppService.mainApp.unregister()
                        print("LaunchAtLogin: Disabled")
                    }
                } catch {
                    print("LaunchAtLogin: Failed to \(newValue ? "enable" : "disable"): \(error)")
                }
            } else {
                // Fallback régebbi macOS-re
                UserDefaults.standard.set(newValue, forKey: "launchAtLogin")
            }
        }
    }
}
