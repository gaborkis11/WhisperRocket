//
//  MenuBarView.swift
//  WhisperRocket
//
//  Created by Gabor Kis on 2025. 12. 26..
//

import SwiftUI

struct MenuBarView: View {
    // Központi app állapot
    @ObservedObject var appState = AppState.shared

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            // Státusz kijelzés
            HStack {
                Circle()
                    .fill(statusColor)
                    .frame(width: 8, height: 8)
                Text(statusText)
                    .font(.headline)
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 4)

            Divider()

            // Hotkey info
            Text("⌃⇧S to record")
                .font(.caption)
                .foregroundColor(.secondary)
                .padding(.horizontal, 8)

            Divider()

            // Settings gomb
            Button("Settings...") {
                SettingsWindowController.shared.showSettings()
            }
            .keyboardShortcut(",", modifiers: .command)

            // History submenu
            Menu("History") {
                Text("No recordings yet")
                    .foregroundColor(.secondary)
            }

            Divider()

            // Quit gomb
            Button("Quit") {
                NSApplication.shared.terminate(nil)
            }
            .keyboardShortcut("q", modifiers: .command)
        }
        .padding(.vertical, 8)
    }

    // Státusz szín
    private var statusColor: Color {
        if appState.isRecording {
            return .red
        } else if appState.isProcessing {
            return .yellow
        } else if appState.isReady {
            return .blue
        } else {
            return .gray
        }
    }

    // Státusz szöveg
    private var statusText: String {
        if appState.isRecording {
            return "Recording..."
        } else if appState.isProcessing {
            return "Processing..."
        } else if appState.isReady {
            return "Ready"
        } else {
            return "Loading..."
        }
    }
}

#Preview {
    MenuBarView()
}
