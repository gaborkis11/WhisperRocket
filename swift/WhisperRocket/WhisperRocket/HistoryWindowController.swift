//
//  HistoryWindowController.swift
//  WhisperRocket
//
//  Created by Gabor Kis on 2025. 12. 27..
//

import Cocoa
import SwiftUI

/// History ablak kezelő
class HistoryWindowController {
    static let shared = HistoryWindowController()

    private var historyWindow: NSWindow?
    private var detailWindow: NSWindow?

    private init() {}

    /// Teljes history lista megjelenítése
    func showHistory() {
        if historyWindow == nil {
            let view = HistoryListView()
            let hostingController = NSHostingController(rootView: view)

            let window = NSWindow(
                contentRect: NSRect(x: 0, y: 0, width: 400, height: 500),
                styleMask: [.titled, .closable, .resizable],
                backing: .buffered,
                defer: false
            )

            window.contentViewController = hostingController
            window.title = "Transcription History"
            window.center()
            window.isReleasedWhenClosed = false

            historyWindow = window
        }

        historyWindow?.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    /// Egy elem részleteinek megjelenítése
    func showDetail(item: HistoryItem) {
        // Előző ablak bezárása ha van
        if let existing = detailWindow {
            existing.close()
            detailWindow = nil
        }

        // Új ablak létrehozása
        let view = HistoryDetailView(item: item)
        let hostingController = NSHostingController(rootView: view)

        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 450, height: 300),
            styleMask: [.titled, .closable, .resizable],
            backing: .buffered,
            defer: false
        )

        window.contentViewController = hostingController
        window.title = "Transcription"
        window.center()
        window.isReleasedWhenClosed = false

        detailWindow = window
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }
}

/// History lista nézet
struct HistoryListView: View {
    @ObservedObject var historyManager = HistoryManager.shared

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Text("Transcription History")
                    .font(.headline)
                Spacer()
                Text("\(historyManager.items.count) items")
                    .foregroundColor(.secondary)
            }
            .padding()

            Divider()

            // Lista
            if historyManager.items.isEmpty {
                Spacer()
                Text("No transcriptions yet")
                    .foregroundColor(.secondary)
                Spacer()
            } else {
                List {
                    ForEach(historyManager.items) { item in
                        HistoryRowView(item: item)
                            .contentShape(Rectangle())
                            .onTapGesture {
                                HistoryWindowController.shared.showDetail(item: item)
                            }
                    }
                    .onDelete { indexSet in
                        for index in indexSet {
                            historyManager.delete(item: historyManager.items[index])
                        }
                    }
                }
            }

            Divider()

            // Footer
            HStack {
                Button("Clear All") {
                    historyManager.clearAll()
                }
                .disabled(historyManager.items.isEmpty)

                Spacer()

                Button("Close") {
                    NSApp.keyWindow?.close()
                }
                .keyboardShortcut(.escape, modifiers: [])
            }
            .padding()
        }
        .frame(minWidth: 350, minHeight: 400)
    }
}

/// History sor nézet
struct HistoryRowView: View {
    let item: HistoryItem

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(item.preview)
                .lineLimit(2)

            Text(item.formattedTime)
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding(.vertical, 4)
    }
}

/// History részlet nézet (teljes szöveg + másolás)
struct HistoryDetailView: View {
    let item: HistoryItem
    @State private var copied = false

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Text(item.formattedTime)
                    .font(.headline)
                Spacer()
            }
            .padding()

            Divider()

            // Szöveg (scrollable, selectable)
            ScrollView {
                Text(item.fullText)
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding()
            }

            Divider()

            // Footer
            HStack {
                Button(copied ? "Copied!" : "Copy to Clipboard") {
                    copyToClipboard()
                }
                .disabled(copied)

                Spacer()

                Button("Close") {
                    NSApp.keyWindow?.close()
                }
                .keyboardShortcut(.escape, modifiers: [])
            }
            .padding()
        }
        .frame(minWidth: 400, minHeight: 250)
    }

    private func copyToClipboard() {
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(item.fullText, forType: .string)

        copied = true

        // 2 másodperc után visszaáll
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
            copied = false
        }
    }
}
