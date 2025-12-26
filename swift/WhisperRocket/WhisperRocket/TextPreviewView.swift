//
//  TextPreviewView.swift
//  WhisperRocket
//
//  Created by Gabor Kis on 2025. 12. 26..
//

import SwiftUI
import AppKit
import Combine

/// Szöveg előnézet és kibővített nézet
struct TextPreviewView: View {
    let text: String
    let isExpanded: Bool

    @EnvironmentObject var controller: PopupWindowController

    // Auto-hide timer
    @State private var countdown: Int = 5
    private let autoHideTimer = Timer.publish(every: 1, on: .main, in: .common).autoconnect()

    // Popup megjelenítési idő (UserDefaults-ból)
    private var displayDuration: Int {
        UserDefaults.standard.integer(forKey: "popupDisplayDuration").clamped(to: 1...30, default: 5)
    }

    var body: some View {
        VStack(spacing: 0) {
            // Fejléc - Done + flat equalizer + (close gomb expanded-nél)
            headerView

            // Elválasztó vonal
            Rectangle()
                .fill(Color(white: 0.24))
                .frame(height: 1)
                .padding(.horizontal, 15)

            if isExpanded {
                expandedContent
            } else {
                previewContent
            }
        }
        .onAppear {
            countdown = displayDuration
        }
        .onReceive(autoHideTimer) { _ in
            if !isExpanded && countdown > 0 {
                countdown -= 1
                if countdown == 0 {
                    controller.hidePopup()
                }
            }
        }
    }

    /// Fejléc nézet
    private var headerView: some View {
        HStack {
            // Done label
            HStack(spacing: 8) {
                Circle()
                    .fill(Color(white: 0.4))
                    .frame(width: 10, height: 10)
                Text("Done")
                    .font(.system(size: 10))
                    .foregroundColor(Color(white: 0.6))
            }

            Spacer()

            // Flat equalizer
            FlatEqualizerView()
                .frame(width: 120, height: 30)

            // Close gomb (csak expanded-nél)
            if isExpanded {
                Button(action: { controller.hidePopup() }) {
                    Circle()
                        .fill(Color(red: 1, green: 0.37, blue: 0.34))
                        .frame(width: 12, height: 12)
                }
                .buttonStyle(.plain)
                .padding(.leading, 8)
            }
        }
        .padding(.horizontal, 15)
        .padding(.vertical, 12)
    }

    /// Előnézet tartalom
    private var previewContent: some View {
        VStack(alignment: .leading, spacing: 8) {
            // Szöveg előnézet (max 40 karakter)
            let displayText = text.count > 40 ? String(text.prefix(40)) + "..." : text
            Text("\"\(displayText)\"")
                .font(.system(size: 11))
                .foregroundColor(.white)
                .lineLimit(1)
                .padding(.horizontal, 15)
                .padding(.top, 8)

            Spacer()

            // Alsó rész - Expand gomb + visszaszámláló
            HStack {
                // Click to expand gomb
                Button(action: { controller.expandText() }) {
                    HStack(spacing: 6) {
                        // Kurzor ikon
                        Image(systemName: "cursorarrow.click")
                            .font(.system(size: 10))
                        Text("Click to expand")
                            .font(.system(size: 10))
                    }
                    .foregroundColor(Color(red: 0.7, green: 0.9, blue: 0.7))
                    .padding(.horizontal, 10)
                    .padding(.vertical, 5)
                    .background(Color(red: 0.3, green: 0.69, blue: 0.31).opacity(0.25))
                    .cornerRadius(4)
                }
                .buttonStyle(.plain)

                Spacer()

                // Visszaszámláló
                Text("\(countdown)s")
                    .font(.system(size: 10))
                    .foregroundColor(Color(red: 0.2, green: 0.2, blue: 0.2))
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color(red: 1, green: 0.76, blue: 0.03).opacity(0.7))
                    .cornerRadius(4)
            }
            .padding(.horizontal, 15)
            .padding(.bottom, 10)
        }
    }

    /// Kibővített tartalom
    private var expandedContent: some View {
        VStack(spacing: 0) {
            // Teljes szöveg (scrollable)
            ScrollView {
                Text(text)
                    .font(.system(size: 11))
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 15)
                    .padding(.top, 10)
            }
            .frame(maxHeight: 100)

            Spacer()

            // Copy gomb középen
            Button(action: copyToClipboard) {
                Text("Copy")
                    .font(.system(size: 10))
                    .foregroundColor(Color(white: 0.78))
                    .padding(.horizontal, 20)
                    .padding(.vertical, 8)
                    .background(Color(white: 0.2))
                    .overlay(
                        RoundedRectangle(cornerRadius: 6)
                            .stroke(Color(white: 0.3), lineWidth: 1)
                    )
                    .cornerRadius(6)
            }
            .buttonStyle(.plain)
            .padding(.bottom, 12)
        }
    }

    /// Szöveg másolása vágólapra
    private func copyToClipboard() {
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(text, forType: .string)
        controller.hidePopup()
    }
}

// MARK: - Helper Extension

extension Int {
    func clamped(to range: ClosedRange<Int>, default defaultValue: Int) -> Int {
        if self == 0 { return defaultValue }
        return Swift.min(Swift.max(self, range.lowerBound), range.upperBound)
    }
}
