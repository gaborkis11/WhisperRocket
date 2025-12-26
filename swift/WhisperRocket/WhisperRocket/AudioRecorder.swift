//
//  AudioRecorder.swift
//  WhisperRocket
//
//  Created by Gabor Kis on 2025. 12. 26..
//

import AVFoundation
import Combine
import Cocoa

/// Hangfelvétel kezelő - AVAudioRecorder alapú implementáció
class AudioRecorder: NSObject, ObservableObject {
    static let shared = AudioRecorder()

    // Állapot
    @Published var isRecording = false
    @Published var hasPermission = false
    @Published var currentAmplitude: Float = 0

    // Callback-ek
    var amplitudeCallback: ((Float) -> Void)?
    var recordingFinishedCallback: ((URL?) -> Void)?

    // Audio recorder
    private var audioRecorder: AVAudioRecorder?
    private var recordingURL: URL?
    private var levelTimer: Timer?

    override private init() {
        super.init()
        checkPermission()
    }

    /// Mikrofon engedély ellenőrzése
    func checkPermission() {
        switch AVCaptureDevice.authorizationStatus(for: .audio) {
        case .authorized:
            hasPermission = true
            print("AudioRecorder: Microphone permission granted")
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: .audio) { [weak self] granted in
                DispatchQueue.main.async {
                    self?.hasPermission = granted
                    print("AudioRecorder: Microphone permission \(granted ? "granted" : "denied")")
                }
            }
        case .denied, .restricted:
            hasPermission = false
            print("AudioRecorder: Microphone permission denied")
        @unknown default:
            hasPermission = false
        }
    }

    /// Felvétel indítása
    func startRecording() {
        guard hasPermission else {
            print("AudioRecorder: No microphone permission")
            checkPermission()
            return
        }

        guard !isRecording else {
            print("AudioRecorder: Already recording")
            return
        }

        // Felvétel mentése a WhisperRocket/recordings mappába
        let recordingsDir = WhisperTranscriber.recordingsDirectory
        let fileName = "recording_\(Date().timeIntervalSince1970).wav"
        recordingURL = recordingsDir.appendingPathComponent(fileName)

        guard let recordingURL = recordingURL else { return }

        // WAV fájl formátum beállítások (16-bit PCM, 16kHz, mono - Whisper optimális)
        let settings: [String: Any] = [
            AVFormatIDKey: Int(kAudioFormatLinearPCM),
            AVSampleRateKey: 16000.0,
            AVNumberOfChannelsKey: 1,
            AVLinearPCMBitDepthKey: 16,
            AVLinearPCMIsFloatKey: false,
            AVLinearPCMIsBigEndianKey: false
        ]

        // Audio recorder létrehozása
        do {
            audioRecorder = try AVAudioRecorder(url: recordingURL, settings: settings)
            audioRecorder?.delegate = self
            audioRecorder?.isMeteringEnabled = true
            audioRecorder?.prepareToRecord()

            if audioRecorder?.record() == true {
                isRecording = true
                startLevelTimer()
                print("AudioRecorder: Recording started -> \(recordingURL.path)")
                print("AudioRecorder: Format: 16kHz, mono, 16-bit PCM")
            } else {
                print("AudioRecorder: Failed to start recording")
            }
        } catch {
            print("AudioRecorder: Failed to create recorder: \(error)")
        }
    }

    /// Felvétel leállítása
    func stopRecording() {
        guard isRecording else { return }

        stopLevelTimer()
        audioRecorder?.stop()
        isRecording = false

        print("AudioRecorder: Recording stopped")

        // Callback a felvétel URL-jével
        DispatchQueue.main.async { [weak self] in
            self?.recordingFinishedCallback?(self?.recordingURL)
        }
    }

    /// Amplitúdó mérés timer
    private func startLevelTimer() {
        levelTimer = Timer.scheduledTimer(withTimeInterval: 0.05, repeats: true) { [weak self] _ in
            guard let self = self, let recorder = self.audioRecorder else { return }

            recorder.updateMeters()
            let db = recorder.averagePower(forChannel: 0)

            // dB -> 0-1 közé normalizálás (-60dB ... 0dB)
            let normalizedAmplitude = max(0, (db + 60) / 60)

            DispatchQueue.main.async {
                self.currentAmplitude = normalizedAmplitude
                self.amplitudeCallback?(normalizedAmplitude)
            }
        }
    }

    /// Timer leállítása
    private func stopLevelTimer() {
        levelTimer?.invalidate()
        levelTimer = nil
        currentAmplitude = 0
    }

    /// Mikrofon beállítások megnyitása
    static func openMicrophoneSettings() {
        if let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone") {
            NSWorkspace.shared.open(url)
        }
    }

    /// Régi felvételek törlése - csak az utolsó 50 marad meg
    func cleanupOldRecordings(keepCount: Int = 50) {
        let recordingsDir = WhisperTranscriber.recordingsDirectory

        do {
            // Összes recording fájl keresése
            let files = try FileManager.default.contentsOfDirectory(at: recordingsDir, includingPropertiesForKeys: [.creationDateKey])
            let recordings = files.filter { $0.lastPathComponent.hasPrefix("recording_") && $0.pathExtension == "wav" }

            // Ha kevesebb van mint a limit, nem csinálunk semmit
            guard recordings.count > keepCount else { return }

            // Rendezés létrehozási dátum szerint (legrégebbi elöl)
            let sortedRecordings = recordings.sorted { file1, file2 in
                let date1 = (try? file1.resourceValues(forKeys: [.creationDateKey]).creationDate) ?? Date.distantPast
                let date2 = (try? file2.resourceValues(forKeys: [.creationDateKey]).creationDate) ?? Date.distantPast
                return date1 < date2
            }

            // Törlendő fájlok (a legrégebbiek)
            let toDelete = sortedRecordings.prefix(recordings.count - keepCount)

            for file in toDelete {
                try FileManager.default.removeItem(at: file)
                print("AudioRecorder: Deleted old recording: \(file.lastPathComponent)")
            }

            if !toDelete.isEmpty {
                print("AudioRecorder: Cleanup complete. Deleted \(toDelete.count) old recordings, kept \(keepCount)")
            }

        } catch {
            print("AudioRecorder: Cleanup error: \(error)")
        }
    }
}

// MARK: - AVAudioRecorderDelegate
extension AudioRecorder: AVAudioRecorderDelegate {
    func audioRecorderDidFinishRecording(_ recorder: AVAudioRecorder, successfully flag: Bool) {
        print("AudioRecorder: Finished recording, success: \(flag)")
    }

    func audioRecorderEncodeErrorDidOccur(_ recorder: AVAudioRecorder, error: Error?) {
        print("AudioRecorder: Encode error: \(error?.localizedDescription ?? "unknown")")
    }
}
