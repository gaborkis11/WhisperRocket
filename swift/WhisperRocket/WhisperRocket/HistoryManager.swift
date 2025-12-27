//
//  HistoryManager.swift
//  WhisperRocket
//
//  Created by Gabor Kis on 2025. 12. 27..
//

import Foundation
import Combine

/// Egy history bejegyzés
struct HistoryItem: Identifiable, Codable {
    let id: UUID
    let timestamp: Date
    let fullText: String

    /// Előnézet (max 40 karakter)
    var preview: String {
        let trimmed = fullText.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.count <= 40 {
            return trimmed
        }
        return String(trimmed.prefix(37)) + "..."
    }

    /// Formázott időpont
    var formattedTime: String {
        let formatter = DateFormatter()
        formatter.dateStyle = .short
        formatter.timeStyle = .short
        return formatter.string(from: timestamp)
    }

    init(fullText: String) {
        self.id = UUID()
        self.timestamp = Date()
        self.fullText = fullText
    }
}

/// Transzkripció history kezelő
class HistoryManager: ObservableObject {
    static let shared = HistoryManager()

    @Published var items: [HistoryItem] = []

    private let maxItems = 50
    private let storageKey = "transcriptionHistory"

    private init() {
        load()
    }

    /// Új transzkripció hozzáadása
    func add(transcription: String) {
        let trimmed = transcription.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }

        let item = HistoryItem(fullText: trimmed)
        items.insert(item, at: 0) // Legújabb elől

        // Max 50 elem
        if items.count > maxItems {
            items = Array(items.prefix(maxItems))
        }

        save()
        print("HistoryManager: Added item, total: \(items.count)")
    }

    /// Egy elem törlése
    func delete(item: HistoryItem) {
        items.removeAll { $0.id == item.id }
        save()
    }

    /// Összes törlése
    func clearAll() {
        items.removeAll()
        save()
        print("HistoryManager: Cleared all items")
    }

    /// Betöltés UserDefaults-ból
    private func load() {
        guard let data = UserDefaults.standard.data(forKey: storageKey) else {
            print("HistoryManager: No saved history")
            return
        }

        do {
            items = try JSONDecoder().decode([HistoryItem].self, from: data)
            print("HistoryManager: Loaded \(items.count) items")
        } catch {
            print("HistoryManager: Failed to load: \(error)")
        }
    }

    /// Mentés UserDefaults-ba
    private func save() {
        do {
            let data = try JSONEncoder().encode(items)
            UserDefaults.standard.set(data, forKey: storageKey)
        } catch {
            print("HistoryManager: Failed to save: \(error)")
        }
    }
}
