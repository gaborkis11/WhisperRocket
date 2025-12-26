//
//  AppState.swift
//  WhisperRocket
//
//  Created by Gabor Kis on 2025. 12. 26..
//

import SwiftUI
import Combine

/// Központi app állapot - minden View innen olvassa az állapotot
class AppState: ObservableObject {
    static let shared = AppState()

    @Published var isRecording = false
    @Published var isProcessing = false
    @Published var isReady = true
    @Published var lastTranscription: String?
    @Published var lastRecordingURL: URL?
    @Published var currentAmplitude: Float = 0

    private var cancellables = Set<AnyCancellable>()

    private init() {
        setupAudioRecorder()
    }

    /// AudioRecorder callback-ek beállítása
    private func setupAudioRecorder() {
        // Amplitúdó callback (equalizer-hez)
        AudioRecorder.shared.amplitudeCallback = { [weak self] amplitude in
            self?.currentAmplitude = amplitude
        }

        // Felvétel befejezése callback
        AudioRecorder.shared.recordingFinishedCallback = { [weak self] url in
            self?.lastRecordingURL = url
            self?.processRecording(url: url)
        }
    }

    /// Felvétel toggle
    func toggleRecording() {
        if isRecording {
            stopRecording()
        } else {
            startRecording()
        }
    }

    /// Felvétel indítása
    func startRecording() {
        isRecording = true
        isReady = false
        print("🎤 Recording started!")
        AudioRecorder.shared.startRecording()
    }

    /// Felvétel leállítása
    func stopRecording() {
        isRecording = false
        isProcessing = true
        print("⏹️ Recording stopped!")
        AudioRecorder.shared.stopRecording()
    }

    /// Felvétel feldolgozása (Whisper transzkripció)
    private func processRecording(url: URL?) {
        guard let url = url else {
            print("❌ No recording URL")
            finishProcessing(transcription: nil)
            return
        }

        print("🚀 Processing: \(url.lastPathComponent)")

        Task {
            // Ha a modell betöltés alatt van, várjunk rá (max 30 sec)
            if ModelManager.shared.isLoading {
                print("⏳ Waiting for model to load...")
                for _ in 0..<60 {
                    try? await Task.sleep(nanoseconds: 500_000_000) // 0.5 sec
                    if !ModelManager.shared.isLoading {
                        print("✅ Model loaded, continuing...")
                        break
                    }
                }
            }

            // Ellenőrizzük, hogy van-e betöltött modell
            if !WhisperTranscriber.shared.isLoaded {
                print("⚠️ No Whisper model loaded. Please download a model in Settings.")
                print("📁 Recording saved: \(url.path)")

                await MainActor.run {
                    self.showNoModelAlert()
                    self.finishProcessing(transcription: nil)
                }
                return
            }

            // WhisperKit transzkripció
            do {
                // Nyelv beolvasása a beállításokból
                let language = UserDefaults.standard.string(forKey: "transcriptionLanguage") ?? "hu"

                let transcription = try await WhisperTranscriber.shared.transcribe(
                    audioURL: url,
                    language: language
                )

                await MainActor.run {
                    self.finishProcessing(transcription: transcription)
                }
            } catch {
                print("❌ Transcription error: \(error)")
                await MainActor.run {
                    self.finishProcessing(transcription: nil)
                }
            }
        }
    }

    /// Feldolgozás befejezése
    private func finishProcessing(transcription: String?) {
        isProcessing = false
        isReady = true
        lastTranscription = transcription
        print("✅ Processing done: \(transcription ?? "nil")")

        // Auto-paste ha van transzkripció
        if let text = transcription, !text.isEmpty {
            PasteManager.shared.pasteText(text)
        }

        // Régi felvételek törlése (csak az utolsó 50 marad)
        AudioRecorder.shared.cleanupOldRecordings(keepCount: 50)
    }

    /// Figyelmeztetés megjelenítése, ha nincs modell betöltve
    private func showNoModelAlert() {
        DispatchQueue.main.async {
            let alert = NSAlert()
            alert.messageText = "No Whisper Model"
            alert.informativeText = "Please download and load a Whisper model in Settings before transcription."
            alert.alertStyle = .warning
            alert.addButton(withTitle: "Open Settings")
            alert.addButton(withTitle: "Cancel")

            NSApp.activate(ignoringOtherApps: true)

            let response = alert.runModal()
            if response == .alertFirstButtonReturn {
                // Settings megnyitása
                SettingsWindowController.shared.showSettings()
            }
        }
    }
}
