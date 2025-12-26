//
//  SettingsView.swift
//  WhisperRocket
//
//  Created by Gabor Kis on 2025. 12. 26..
//

import SwiftUI

/// Settings ablak fő nézete
struct SettingsView: View {
    @StateObject private var modelManager = ModelManager.shared
    @State private var selectedLanguage: String

    let availableLanguages = [
        ("hu", "Magyar"),
        ("en", "English"),
        ("de", "Deutsch"),
        ("fr", "Français"),
        ("es", "Español"),
        ("it", "Italiano"),
        ("auto", "Auto-detect")
    ]

    init() {
        // Nyelv betöltése UserDefaults-ból
        let savedLanguage = UserDefaults.standard.string(forKey: "transcriptionLanguage") ?? "hu"
        _selectedLanguage = State(initialValue: savedLanguage)
    }

    var body: some View {
        TabView {
            // General tab (első - fontosabb)
            GeneralTabView(selectedLanguage: $selectedLanguage, availableLanguages: availableLanguages)
                .tabItem {
                    Label("General", systemImage: "gear")
                }

            // Models tab (második)
            ModelsTabView()
                .tabItem {
                    Label("Models", systemImage: "cpu")
                }
        }
        .frame(width: 550, height: 500)
        .padding()
        .onChange(of: selectedLanguage) { _, newValue in
            // Nyelv mentése UserDefaults-ba
            UserDefaults.standard.set(newValue, forKey: "transcriptionLanguage")
            print("Language changed to: \(newValue)")
        }
    }
}

/// Models tab - modell letöltés és kiválasztás
struct ModelsTabView: View {
    @StateObject private var modelManager = ModelManager.shared

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Whisper Models")
                .font(.headline)

            Text("Select and download a model to enable transcription.")
                .font(.caption)
                .foregroundColor(.secondary)

            // Modell lista
            List {
                ForEach(ModelManager.availableModels, id: \.name) { model in
                    ModelRowView(model: model)
                }
            }
            .listStyle(.inset)

            // Aktív modell info
            if let activeModel = modelManager.activeModelName {
                HStack {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.green)
                    Text("Active: \(activeModel)")
                        .font(.caption)
                }
            } else {
                HStack {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundColor(.orange)
                    Text("No model loaded. Download a model to start.")
                        .font(.caption)
                }
            }

            Spacer()
        }
        .padding()
    }
}

/// Egy modell sor a listában
struct ModelRowView: View {
    let model: WhisperModel
    @StateObject private var modelManager = ModelManager.shared

    var isDownloaded: Bool {
        modelManager.downloadedModels.contains(model.name)
    }

    var isActive: Bool {
        modelManager.activeModelName == model.name
    }

    var isDownloading: Bool {
        modelManager.downloadingModel == model.name
    }

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                // Modell név + Recommended badge + Active jelzés
                HStack(spacing: 6) {
                    Text(model.displayName)
                        .font(.headline)

                    // Recommended badge
                    if model.isRecommended {
                        Text("Recommended")
                            .font(.caption2)
                            .fontWeight(.medium)
                            .foregroundColor(.white)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Color.blue)
                            .cornerRadius(4)
                    }

                    // Active jelzés
                    if isActive {
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundColor(.green)
                            .font(.caption)
                    }
                }

                // Leírás
                Text(model.description)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .lineLimit(2)

                // Méret
                Text(model.size)
                    .font(.caption)
                    .fontWeight(.medium)
                    .foregroundColor(.orange)
            }

            Spacer()

            // Státusz és gombok
            if isDownloading {
                ProgressView()
                    .scaleEffect(0.7)
                Text("\(Int(modelManager.downloadProgress * 100))%")
                    .font(.caption)
                    .frame(width: 40)
            } else if isDownloaded {
                HStack(spacing: 8) {
                    if isActive {
                        Text("Active")
                            .font(.caption)
                            .fontWeight(.medium)
                            .foregroundColor(.green)
                    } else {
                        Button("Activate") {
                            Task {
                                await modelManager.loadModel(name: model.name)
                            }
                        }
                        .buttonStyle(.bordered)
                    }

                    // Törlés gomb
                    Button {
                        modelManager.deleteModel(name: model.name)
                    } label: {
                        Image(systemName: "trash")
                            .foregroundColor(.red)
                    }
                    .buttonStyle(.borderless)
                    .help("Delete model")
                }
            } else {
                Button("Download") {
                    Task {
                        await modelManager.downloadModel(name: model.name)
                    }
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .padding(.vertical, 6)
    }
}

/// General tab - általános beállítások
struct GeneralTabView: View {
    @Binding var selectedLanguage: String
    let availableLanguages: [(String, String)]

    var body: some View {
        Form {
            Section("Transcription") {
                Picker("Language", selection: $selectedLanguage) {
                    ForEach(availableLanguages, id: \.0) { code, name in
                        Text(name).tag(code)
                    }
                }
                .pickerStyle(.menu)
            }

            Section("Hotkey") {
                HStack {
                    Text("Current hotkey:")
                    Spacer()
                    Text("⌃⇧S")
                        .font(.system(.body, design: .monospaced))
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.gray.opacity(0.2))
                        .cornerRadius(4)
                }
                Text("Hotkey configuration coming soon...")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Section("About") {
                HStack {
                    Text("WhisperRocket")
                    Spacer()
                    Text("v1.0.0")
                        .foregroundColor(.secondary)
                }
                HStack {
                    Text("Powered by")
                    Spacer()
                    Text("WhisperKit + CoreML")
                        .foregroundColor(.secondary)
                }
            }
        }
        .formStyle(.grouped)
        .padding()
    }
}

#Preview {
    SettingsView()
}
