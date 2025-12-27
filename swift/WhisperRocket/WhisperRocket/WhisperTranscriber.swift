//
//  WhisperTranscriber.swift
//  WhisperRocket
//
//  Created by Gabor Kis on 2025. 12. 26..
//

import Foundation
import Combine
import WhisperKit

/// Whisper transzkripció kezelő - WhisperKit alapú implementáció
class WhisperTranscriber: ObservableObject {
    static let shared = WhisperTranscriber()

    // Állapot
    @Published var isLoaded = false
    @Published var isTranscribing = false
    @Published var loadingProgress: Float = 0
    @Published var partialText: String = ""

    // WhisperKit instance
    private var whisperKit: WhisperKit?

    // Alapértelmezett modell
    private let defaultModel = "large-v3-turbo"

    // WhisperRocket mappa (Documents-ben) - felvételeknek
    static var appDirectory: URL {
        let documentsDir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first!
        let appDir = documentsDir.appendingPathComponent("WhisperRocket")

        // Létrehozás ha nem létezik
        if !FileManager.default.fileExists(atPath: appDir.path) {
            try? FileManager.default.createDirectory(at: appDir, withIntermediateDirectories: true)
        }

        return appDir
    }

    // Felvételek tárolási helye
    static var recordingsDirectory: URL {
        let recordingsDir = appDirectory.appendingPathComponent("recordings")

        // Létrehozás ha nem létezik
        if !FileManager.default.fileExists(atPath: recordingsDir.path) {
            try? FileManager.default.createDirectory(at: recordingsDir, withIntermediateDirectories: true)
        }

        return recordingsDir
    }

    private init() {}

    /// Modell betöltése
    func loadModel(name: String? = nil) async throws {
        let modelName = name ?? defaultModel
        let modelFolder = ModelManager.modelFolder(for: modelName)

        print("WhisperTranscriber: Loading model '\(modelName)' from \(modelFolder.path)...")

        await MainActor.run {
            self.loadingProgress = 0
        }

        // WhisperKit inicializálása a már letöltött modellből
        // FONTOS: download: false - NEM töltünk le újra, a ModelManager már letöltötte
        // FONTOS: downloadBase - a tokenizer is ide töltődjön, NE a Documents/huggingface-be!
        whisperKit = try await WhisperKit(
            downloadBase: ModelManager.downloadBase,
            modelFolder: modelFolder.path,
            verbose: true,
            logLevel: .debug,
            prewarm: true,
            load: true,
            download: false
        )

        await MainActor.run {
            self.isLoaded = true
            self.loadingProgress = 1.0
        }

        print("WhisperTranscriber: Model '\(modelName)' loaded successfully!")
    }

    /// Audio fájl transzkripciója
    func transcribe(audioURL: URL, language: String = "hu") async throws -> String {
        guard let whisperKit = whisperKit else {
            throw WhisperTranscriberError.modelNotLoaded
        }

        await MainActor.run {
            self.isTranscribing = true
            self.partialText = ""
        }

        defer {
            Task { @MainActor in
                self.isTranscribing = false
                self.partialText = ""
            }
        }

        print("WhisperTranscriber: Transcribing \(audioURL.lastPathComponent)...")

        // Transzkripció opciók
        let options = DecodingOptions(
            verbose: true,
            task: .transcribe,
            language: language,
            temperatureFallbackCount: 3,
            sampleLength: 224,
            usePrefillPrompt: true,
            usePrefillCache: true,
            skipSpecialTokens: true,
            withoutTimestamps: true
        )

        // Transzkripció futtatása callback-kel a progress frissítéséhez
        let results = try await whisperKit.transcribe(
            audioPath: audioURL.path,
            decodeOptions: options,
            callback: { [weak self] progress in
                Task { @MainActor in
                    self?.partialText = progress.text
                }
                return true
            }
        )

        // Eredmény összeállítása
        let transcription = results.map { $0.text }.joined(separator: " ")

        print("WhisperTranscriber: Transcription complete: '\(transcription)'")

        return transcription.trimmingCharacters(in: CharacterSet.whitespacesAndNewlines)
    }

    /// Modell eltávolítása a memóriából
    func unloadModel() {
        whisperKit = nil
        isLoaded = false
        print("WhisperTranscriber: Model unloaded")
    }
}

// MARK: - Errors
enum WhisperTranscriberError: Error, LocalizedError {
    case modelNotLoaded
    case transcriptionFailed(String)

    var errorDescription: String? {
        switch self {
        case .modelNotLoaded:
            return "Whisper model is not loaded"
        case .transcriptionFailed(let reason):
            return "Transcription failed: \(reason)"
        }
    }
}
