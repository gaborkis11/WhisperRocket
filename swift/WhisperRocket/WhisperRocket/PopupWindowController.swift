//
//  PopupWindowController.swift
//  WhisperRocket
//
//  Created by Gabor Kis on 2025. 12. 26..
//

import Cocoa
import SwiftUI
import Combine

/// Popup ablak állapotok
enum PopupState: Equatable {
    case hidden
    case recording
    case processing
    case textPreview(text: String)
    case textExpanded(text: String)
}

/// Custom NSWindow - nem vesz fókuszt
class PopupWindow: NSWindow {
    override var canBecomeKey: Bool { false }
    override var canBecomeMain: Bool { false }
}

/// Popup ablak kezelő - felvétel/processing/transzkripció megjelenítése
class PopupWindowController: ObservableObject {
    static let shared = PopupWindowController()

    private var window: PopupWindow?
    private var cancellables = Set<AnyCancellable>()

    // Méretek
    private let baseWidth: CGFloat = 350
    private let baseHeight: CGFloat = 100
    private let previewHeight: CGFloat = 200
    private let expandedHeight: CGFloat = 250

    // Mentett pozíció (session alatt megmarad)
    private var savedPosition: NSPoint?

    // Állapot
    @Published var state: PopupState = .hidden
    @Published var currentAmplitude: Float = 0

    private init() {
        setupBindings()
    }

    /// AppState változások figyelése
    private func setupBindings() {
        // isRecording változás
        AppState.shared.$isRecording
            .removeDuplicates()
            .receive(on: DispatchQueue.main)
            .sink { [weak self] isRecording in
                if isRecording {
                    self?.showRecording()
                }
            }
            .store(in: &cancellables)

        // isProcessing változás
        AppState.shared.$isProcessing
            .removeDuplicates()
            .receive(on: DispatchQueue.main)
            .sink { [weak self] isProcessing in
                if isProcessing {
                    self?.showProcessing()
                }
            }
            .store(in: &cancellables)

        // lastTranscription változás
        AppState.shared.$lastTranscription
            .receive(on: DispatchQueue.main)
            .sink { [weak self] transcription in
                if let text = transcription, !text.isEmpty {
                    self?.showTextPreview(text: text)
                }
            }
            .store(in: &cancellables)

        // Amplitúdó frissítése
        AppState.shared.$currentAmplitude
            .receive(on: DispatchQueue.main)
            .sink { [weak self] amplitude in
                self?.currentAmplitude = amplitude
            }
            .store(in: &cancellables)
    }

    /// Ablak létrehozása ha szükséges
    private func ensureWindow() {
        if window == nil {
            createWindow()
        }
    }

    /// Új popup ablak létrehozása
    private func createWindow() {
        let popupView = PopupView()
            .environmentObject(self)

        let hostingController = NSHostingController(rootView: popupView)

        let newWindow = PopupWindow(
            contentRect: NSRect(x: 0, y: 0, width: baseWidth, height: baseHeight),
            styleMask: [.borderless],
            backing: .buffered,
            defer: false
        )

        newWindow.contentViewController = hostingController
        newWindow.isOpaque = false
        newWindow.backgroundColor = .clear
        newWindow.level = .floating
        newWindow.hasShadow = true
        newWindow.isMovableByWindowBackground = true
        newWindow.collectionBehavior = [.canJoinAllSpaces, .stationary]

        self.window = newWindow
    }

    /// Pozíció beállítása (képernyő jobb felső sarka vagy mentett)
    private func positionWindow() {
        guard let window = window else { return }

        if let saved = savedPosition {
            window.setFrameOrigin(saved)
        } else {
            // Képernyő jobb felső sarka
            if let screen = NSScreen.main {
                let screenFrame = screen.visibleFrame
                let x = screenFrame.maxX - baseWidth - 20
                let y = screenFrame.maxY - window.frame.height - 20
                window.setFrameOrigin(NSPoint(x: x, y: y))
            }
        }
    }

    /// Ablak méretének frissítése
    private func resizeWindow(height: CGFloat) {
        guard let window = window else { return }
        var frame = window.frame
        let heightDiff = height - frame.height
        frame.size.height = height
        frame.origin.y -= heightDiff // Felfelé nő
        window.setFrame(frame, display: true, animate: true)
    }

    // MARK: - Állapot váltások

    /// Recording állapot megjelenítése
    func showRecording() {
        ensureWindow()
        state = .recording
        resizeWindow(height: baseHeight)
        positionWindow()
        window?.orderFront(nil)
    }

    /// Processing állapot megjelenítése
    func showProcessing() {
        ensureWindow()
        state = .processing
        resizeWindow(height: baseHeight)
        window?.orderFront(nil)
    }

    /// Szöveg előnézet megjelenítése
    func showTextPreview(text: String) {
        ensureWindow()
        state = .textPreview(text: text)
        resizeWindow(height: previewHeight)
        window?.orderFront(nil)
    }

    /// Szöveg kibővített nézet
    func expandText() {
        guard case .textPreview(let text) = state else { return }
        state = .textExpanded(text: text)
        resizeWindow(height: expandedHeight)
    }

    /// Popup elrejtése
    func hidePopup() {
        // Pozíció mentése
        if let window = window {
            savedPosition = window.frame.origin
        }
        state = .hidden
        window?.orderOut(nil)
    }

    /// Pozíció mentése (húzás után)
    func savePosition() {
        if let window = window {
            savedPosition = window.frame.origin
        }
    }
}
