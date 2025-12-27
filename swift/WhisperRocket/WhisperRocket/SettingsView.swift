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

    // Popup megjelenítési idő (1-30 másodperc)
    @State private var popupDuration: Double

    // Hotkey beállítás
    @State private var isRecordingHotkey = false
    @State private var currentHotkey: String

    // Launch at Login
    @State private var launchAtLogin: Bool

    init(selectedLanguage: Binding<String>, availableLanguages: [(String, String)]) {
        self._selectedLanguage = selectedLanguage
        self.availableLanguages = availableLanguages

        // Popup idő betöltése
        let savedDuration = UserDefaults.standard.integer(forKey: "popupDisplayDuration")
        _popupDuration = State(initialValue: Double(savedDuration > 0 ? savedDuration : 5))

        // Hotkey betöltése
        let savedHotkey = UserDefaults.standard.string(forKey: "hotkey") ?? "ctrl+shift+s"
        _currentHotkey = State(initialValue: savedHotkey)

        // Launch at Login betöltése
        _launchAtLogin = State(initialValue: LaunchAtLoginManager.isEnabled)
    }

    var body: some View {
        Form {
            Section("Transcription") {
                Picker("Language", selection: $selectedLanguage) {
                    ForEach(availableLanguages, id: \.0) { code, name in
                        Text(name).tag(code)
                    }
                }
                .pickerStyle(.menu)

                Text("Transcription will be generated in the selected language")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Section("Hotkey") {
                HStack {
                    Text("Current hotkey:")
                    Spacer()
                    Text(hotkeyDisplayString)
                        .font(.system(.body, design: .monospaced))
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.gray.opacity(0.2))
                        .cornerRadius(4)
                }

                Text("Press once to start recording, press again to stop and transcribe")
                    .font(.caption)
                    .foregroundColor(.secondary)

                HotkeyRecorderView(currentHotkey: $currentHotkey)
            }

            Section("Popup") {
                HStack {
                    Text("Display duration")
                    Spacer()
                    Text("\(Int(popupDuration))s")
                        .font(.system(.body, design: .monospaced))
                        .foregroundColor(.secondary)
                        .frame(width: 30, alignment: .trailing)
                }

                Slider(value: $popupDuration, in: 1...30)
                    .onChange(of: popupDuration) { _, newValue in
                        let rounded = round(newValue)
                        if popupDuration != rounded {
                            popupDuration = rounded
                        }
                        UserDefaults.standard.set(Int(rounded), forKey: "popupDisplayDuration")
                    }

                Text("How long the text preview stays visible after transcription")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Section("Startup") {
                Toggle("Launch at Login", isOn: $launchAtLogin)
                    .onChange(of: launchAtLogin) { _, newValue in
                        LaunchAtLoginManager.isEnabled = newValue
                    }

                Text("Automatically start WhisperRocket when you log in")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .formStyle(.grouped)
        .padding()
    }

    // Hotkey megjelenítése szép formában
    private var hotkeyDisplayString: String {
        var parts: [String] = []
        let lowercased = currentHotkey.lowercased()

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

        // Utolsó karakter (a billentyű)
        if let lastPart = currentHotkey.split(separator: "+").last {
            parts.append(lastPart.uppercased())
        }

        return parts.joined()
    }
}

/// Hotkey felvevő nézet
struct HotkeyRecorderView: View {
    @Binding var currentHotkey: String
    @State private var isRecording = false
    @FocusState private var isFocused: Bool

    var body: some View {
        HStack {
            Text("Set new hotkey:")
            Spacer()

            Button(isRecording ? "Press keys..." : "Click to record") {
                isRecording = true
                isFocused = true
            }
            .buttonStyle(.bordered)
            .background(
                HotkeyListenerView(isRecording: $isRecording, onHotkeyRecorded: { hotkey in
                    currentHotkey = hotkey
                    UserDefaults.standard.set(hotkey, forKey: "hotkey")
                    // HotkeyManager újraindítása
                    HotkeyManager.shared.stopListening()
                    HotkeyManager.shared.startListening()
                    print("Hotkey changed to: \(hotkey)")
                })
                .frame(width: 0, height: 0)
            )
        }

        if isRecording {
            Text("Press Ctrl/Cmd/Alt/Shift + a key, then release")
                .font(.caption)
                .foregroundColor(.orange)
        }
    }
}

/// NSView wrapper a hotkey figyeléséhez
struct HotkeyListenerView: NSViewRepresentable {
    @Binding var isRecording: Bool
    var onHotkeyRecorded: (String) -> Void

    func makeNSView(context: Context) -> HotkeyListenerNSView {
        let view = HotkeyListenerNSView()
        view.onHotkeyRecorded = { hotkey in
            onHotkeyRecorded(hotkey)
            isRecording = false
        }
        return view
    }

    func updateNSView(_ nsView: HotkeyListenerNSView, context: Context) {
        nsView.isRecording = isRecording
        if isRecording {
            nsView.window?.makeFirstResponder(nsView)
        }
    }
}

/// NSView a billentyű figyeléséhez
class HotkeyListenerNSView: NSView {
    var isRecording = false
    var onHotkeyRecorded: ((String) -> Void)?

    override var acceptsFirstResponder: Bool { true }

    override func keyDown(with event: NSEvent) {
        guard isRecording else {
            super.keyDown(with: event)
            return
        }

        // Modifier-ek ellenőrzése
        let modifiers = event.modifierFlags
        var parts: [String] = []

        if modifiers.contains(.control) {
            parts.append("ctrl")
        }
        if modifiers.contains(.shift) {
            parts.append("shift")
        }
        if modifiers.contains(.option) {
            parts.append("alt")
        }
        if modifiers.contains(.command) {
            parts.append("cmd")
        }

        // Legalább egy modifier kell
        guard !parts.isEmpty else { return }

        // Billentyű hozzáadása
        if let characters = event.charactersIgnoringModifiers?.lowercased(),
           !characters.isEmpty,
           characters != " " {
            parts.append(characters)

            let hotkey = parts.joined(separator: "+")
            onHotkeyRecorded?(hotkey)
        }
    }
}

#Preview {
    SettingsView()
}
