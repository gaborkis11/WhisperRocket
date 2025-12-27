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
    @ObservedObject var historyManager = HistoryManager.shared

    // Aktuális hotkey megjelenítése
    private var hotkeyDisplay: String {
        let hotkey = UserDefaults.standard.string(forKey: "hotkey") ?? "ctrl+shift+s"
        var parts: [String] = []
        let lowercased = hotkey.lowercased()

        if lowercased.contains("ctrl") || lowercased.contains("control") {
            parts.append("⌃")
        }
        if lowercased.contains("shift") {
            parts.append("⇧")
        }
        if lowercased.contains("alt") || lowercased.contains("option") {
            parts.append("⌥")
        }
        if lowercased.contains("cmd") || lowercased.contains("command") {
            parts.append("⌘")
        }
        if let lastPart = hotkey.split(separator: "+").last {
            parts.append(lastPart.uppercased())
        }
        return parts.joined()
    }

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
            Text("\(hotkeyDisplay) to record")
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
                if historyManager.items.isEmpty {
                    Text("No transcriptions yet")
                        .foregroundColor(.secondary)
                } else {
                    // Utolsó 10 elem megjelenítése a menüben
                    ForEach(historyManager.items.prefix(10)) { item in
                        Button {
                            // Késleltetés, hogy a menü bezáródjon előbb
                            DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                                HistoryWindowController.shared.showDetail(item: item)
                            }
                        } label: {
                            Text(item.preview)
                        }
                    }

                    if historyManager.items.count > 10 {
                        Divider()
                        Button("Show All (\(historyManager.items.count))...") {
                            DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                                HistoryWindowController.shared.showHistory()
                            }
                        }
                    }

                    Divider()

                    Button("Clear All") {
                        historyManager.clearAll()
                    }
                }
            }

            // About
            Button("About") {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                    AboutWindowController.shared.showAbout()
                }
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
            return .green
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
