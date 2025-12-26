//
//  ModelManager.swift
//  WhisperRocket
//
//  Created by Gabor Kis on 2025. 12. 26..
//

import Foundation
import Combine
import WhisperKit

/// Whisper modell információ
struct WhisperModel {
    let name: String
    let displayName: String
    let description: String
    let size: String
    let isRecommended: Bool
}

/// Modell kezelő - letöltés, betöltés, törlés
class ModelManager: ObservableObject {
    static let shared = ModelManager()

    // Elérhető modellek - sorrendben a legjobbaktól
    static let availableModels: [WhisperModel] = [
        // Legjobb választás nem-angol nyelvekhez
        WhisperModel(
            name: "large-v3",
            displayName: "Large v3",
            description: "Best accuracy for all languages. Recommended for Hungarian and other non-English languages.",
            size: "~3 GB",
            isRecommended: true
        ),
        // Gyors alternatíva
        WhisperModel(
            name: "large-v3-turbo",
            displayName: "Large v3 Turbo",
            description: "8x faster than Large v3, but slightly lower accuracy on non-English. Good for English.",
            size: "~1.5 GB",
            isRecommended: false
        ),
        // Közepes
        WhisperModel(
            name: "medium",
            displayName: "Medium",
            description: "Good balance of speed and accuracy. Suitable for most use cases.",
            size: "~1.5 GB",
            isRecommended: false
        ),
        // Kisebb modellek
        WhisperModel(
            name: "small",
            displayName: "Small",
            description: "Fast with reasonable accuracy. Good for quick transcriptions.",
            size: "~500 MB",
            isRecommended: false
        ),
        WhisperModel(
            name: "base",
            displayName: "Base",
            description: "Very fast, moderate accuracy. Best for short phrases.",
            size: "~150 MB",
            isRecommended: false
        ),
        WhisperModel(
            name: "tiny",
            displayName: "Tiny",
            description: "Fastest model, lowest accuracy. For testing or very fast needs.",
            size: "~75 MB",
            isRecommended: false
        )
    ]

    // Állapot
    @Published var downloadedModels: Set<String> = []
    @Published var activeModelName: String? {
        didSet {
            // Mentés UserDefaults-ba
            UserDefaults.standard.set(activeModelName, forKey: "activeModelName")
        }
    }
    @Published var downloadingModel: String?
    @Published var downloadProgress: Float = 0
    @Published var isLoading = false
    @Published var errorMessage: String?

    // Flag a dupla betöltés megakadályozására
    private var isRestoringModel = false

    /// Alap mappa az Application Support-ban (rejtett, nem a Documents-ben!)
    /// A HubApi ide tölti a modelleket: downloadBase/models/argmaxinc/whisperkit-coreml/
    static var downloadBase: URL {
        let appSupport = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        let baseDir = appSupport.appendingPathComponent("WhisperRocket")

        // Létrehozás ha nem létezik
        if !FileManager.default.fileExists(atPath: baseDir.path) {
            try? FileManager.default.createDirectory(at: baseDir, withIntermediateDirectories: true)
        }

        return baseDir
    }

    private init() {
        // Ellenőrizzük a már letöltött modelleket
        checkDownloadedModels()

        // Előző aktív modell visszaállítása
        if let savedModelName = UserDefaults.standard.string(forKey: "activeModelName"),
           downloadedModels.contains(savedModelName) {
            print("ModelManager: Restoring previous active model: \(savedModelName)")
            isRestoringModel = true
            // Aszinkron betöltés
            Task {
                await loadModel(name: savedModelName)
                await MainActor.run {
                    self.isRestoringModel = false
                }
            }
        }
    }

    /// Modellek cache mappája (Application Support-ban)
    /// HubApi struktúra: downloadBase/models/argmaxinc/whisperkit-coreml/
    static var modelsDirectory: URL {
        return downloadBase.appendingPathComponent("models/argmaxinc/whisperkit-coreml")
    }

    /// Konkrét modell mappa elérési útja
    static func modelFolder(for name: String) -> URL {
        return modelsDirectory.appendingPathComponent("openai_whisper-\(name)")
    }

    /// Letöltött modellek ellenőrzése a fájlrendszerben
    func checkDownloadedModels() {
        print("ModelManager: Checking downloaded models...")

        let cacheDir = Self.modelsDirectory

        print("ModelManager: Checking cache at: \(cacheDir.path)")

        // Modell nevek mapping (WhisperKit formátum → mi formátumunk)
        let modelNameMapping: [String: String] = [
            "openai_whisper-tiny": "tiny",
            "openai_whisper-base": "base",
            "openai_whisper-small": "small",
            "openai_whisper-medium": "medium",
            "openai_whisper-large-v3": "large-v3",
            "openai_whisper-large-v3-turbo": "large-v3-turbo"
        ]

        // Ellenőrizzük, mely modellek léteznek
        if let contents = try? FileManager.default.contentsOfDirectory(atPath: cacheDir.path) {
            for folder in contents {
                if let modelName = modelNameMapping[folder] {
                    downloadedModels.insert(modelName)
                    print("ModelManager: Found downloaded model: \(modelName)")
                }
            }
        }

        print("ModelManager: Downloaded models: \(downloadedModels)")
    }

    /// Modell letöltése
    func downloadModel(name: String) async {
        await MainActor.run {
            self.downloadingModel = name
            self.downloadProgress = 0
            self.errorMessage = nil
        }

        print("ModelManager: Downloading model '\(name)' to \(Self.downloadBase.path)...")

        do {
            // WhisperKit.download() - downloadBase paraméterrel a rejtett Application Support mappába tölti
            let modelPath = try await WhisperKit.download(
                variant: name,
                downloadBase: Self.downloadBase,
                progressCallback: { progress in
                    DispatchQueue.main.async {
                        self.downloadProgress = Float(progress.fractionCompleted)
                    }
                }
            )

            print("ModelManager: Model downloaded to: \(modelPath)")

            await MainActor.run {
                self.downloadedModels.insert(name)
                self.downloadingModel = nil
                self.downloadProgress = 1.0
            }

            print("ModelManager: Model '\(name)' downloaded successfully!")

            // Automatikusan betöltjük
            if self.activeModelName == nil {
                await loadModel(name: name)
            }

        } catch {
            await MainActor.run {
                self.downloadingModel = nil
                self.errorMessage = "Failed to download model: \(error.localizedDescription)"
            }
            print("ModelManager: Download error: \(error)")
        }
    }

    /// Modell betöltése
    func loadModel(name: String) async {
        // Ha már ez a modell aktív, nem töltjük újra
        if activeModelName == name && WhisperTranscriber.shared.isLoaded {
            print("ModelManager: Model '\(name)' already active, skipping reload")
            return
        }

        await MainActor.run {
            self.isLoading = true
            self.errorMessage = nil
        }

        print("ModelManager: Loading model '\(name)'...")

        do {
            try await WhisperTranscriber.shared.loadModel(name: name)

            await MainActor.run {
                self.activeModelName = name
                self.downloadedModels.insert(name)
                self.isLoading = false
            }

            print("ModelManager: Model '\(name)' loaded and active!")

        } catch {
            await MainActor.run {
                self.isLoading = false
                self.errorMessage = "Failed to load model: \(error.localizedDescription)"
            }
            print("ModelManager: Load error: \(error)")
        }
    }

    /// Modell eltávolítása
    func deleteModel(name: String) {
        // Ha aktív, először unload
        if activeModelName == name {
            activeModelName = nil
            WhisperTranscriber.shared.unloadModel()
        }

        // Modell mappa elérési útja
        let modelPath = Self.modelFolder(for: name)

        do {
            if FileManager.default.fileExists(atPath: modelPath.path) {
                try FileManager.default.removeItem(at: modelPath)
                print("ModelManager: Deleted model folder: \(modelPath.path)")
            }
        } catch {
            print("ModelManager: Failed to delete model folder: \(error)")
        }

        // Törlés a Set-ből
        downloadedModels.remove(name)

        print("ModelManager: Model '\(name)' removed")
    }
}
