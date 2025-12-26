//
//  WhisperRocketApp.swift
//  WhisperRocket
//
//  Created by Gabor Kis on 2025. 12. 26..
//

import SwiftUI

@main
struct WhisperRocketApp: App {
    // AppDelegate a hotkey listener és egyéb rendszer funkciókhoz
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    // AppState figyelése az ikon dinamikus változtatásához
    @ObservedObject private var appState = AppState.shared

    var body: some Scene {
        // Menu bar app - dinamikus ikon az állapot alapján
        MenuBarExtra("WhisperRocket", systemImage: menuBarIcon) {
            MenuBarView()
        }
        .menuBarExtraStyle(.menu)
    }

    /// Dinamikus ikon az állapot alapján
    private var menuBarIcon: String {
        if appState.isRecording {
            return "record.circle.fill"  // Felvétel közben
        } else if appState.isProcessing {
            return "ellipsis.circle.fill"  // Feldolgozás közben
        } else {
            return "mic.fill"  // Készenléti állapot
        }
    }
}
