//
//  PopupView.swift
//  WhisperRocket
//
//  Created by Gabor Kis on 2025. 12. 26..
//

import SwiftUI

/// Fő popup nézet - állapot alapján rendereli a megfelelő tartalmat
struct PopupView: View {
    @EnvironmentObject var controller: PopupWindowController

    // Fix méretek
    private let baseWidth: CGFloat = 350
    private let baseHeight: CGFloat = 100
    private let previewHeight: CGFloat = 140
    private let expandedHeight: CGFloat = 220

    private var currentHeight: CGFloat {
        switch controller.state {
        case .hidden, .recording, .processing:
            return baseHeight
        case .textPreview:
            return previewHeight
        case .textExpanded:
            return expandedHeight
        }
    }

    var body: some View {
        ZStack {
            // Háttér - sötét, lekerekített
            RoundedRectangle(cornerRadius: 12)
                .fill(Color(red: 0.1, green: 0.1, blue: 0.1).opacity(0.94))

            // Tartalom állapot alapján
            switch controller.state {
            case .hidden:
                EmptyView()

            case .recording:
                RecordingView()
                    .environmentObject(controller)

            case .processing:
                ProcessingView()

            case .textPreview(let text):
                TextPreviewView(text: text, isExpanded: false)
                    .environmentObject(controller)

            case .textExpanded(let text):
                TextPreviewView(text: text, isExpanded: true)
                    .environmentObject(controller)
            }
        }
        .frame(width: baseWidth, height: currentHeight)
    }
}

/// Recording nézet - equalizer + recording label
struct RecordingView: View {
    @EnvironmentObject var controller: PopupWindowController

    // Hotkey megjelenítéshez
    private var hotkeyDisplay: String {
        let hotkey = UserDefaults.standard.string(forKey: "hotkey") ?? "ctrl+shift+s"
        return hotkey.split(separator: "+").map { $0.capitalized }.joined(separator: "+")
    }

    var body: some View {
        VStack(spacing: 0) {
            // Equalizer - felső rész
            EqualizerView()
                .environmentObject(controller)
                .frame(height: 55)

            Spacer()

            // Alsó rész - Recording label + hotkey gombok
            HStack {
                // Piros kör + Recording
                HStack(spacing: 8) {
                    Circle()
                        .fill(Color.red)
                        .frame(width: 10, height: 10)
                    Text("Recording")
                        .font(.system(size: 10))
                        .foregroundColor(Color(white: 0.6))
                }

                Spacer()

                // Finish gomb
                HStack(spacing: 4) {
                    Text("Finish")
                        .font(.system(size: 9))
                        .foregroundColor(Color(white: 0.5))
                    Text(hotkeyDisplay)
                        .font(.system(size: 9))
                        .foregroundColor(Color(white: 0.7))
                        .padding(.horizontal, 6)
                        .padding(.vertical, 3)
                        .background(Color(white: 0.3).opacity(0.6))
                        .cornerRadius(4)
                }

                // Cancel gomb
                HStack(spacing: 4) {
                    Text("Cancel")
                        .font(.system(size: 9))
                        .foregroundColor(Color(white: 0.5))
                    Text("Esc")
                        .font(.system(size: 9))
                        .foregroundColor(Color(white: 0.7))
                        .padding(.horizontal, 6)
                        .padding(.vertical, 3)
                        .background(Color(white: 0.3).opacity(0.6))
                        .cornerRadius(4)
                }
            }
            .padding(.horizontal, 15)
            .padding(.bottom, 10)
        }
    }
}
