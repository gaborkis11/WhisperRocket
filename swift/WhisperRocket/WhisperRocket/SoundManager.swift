//
//  SoundManager.swift
//  WhisperRocket
//
//  Created by Gabor Kis on 2025. 12. 27..
//

import AVFoundation

/// Hangjelzések kezelése - start/stop hangok felvétel indításakor és leállításakor
class SoundManager {
    static let shared = SoundManager()

    private var startPlayer: AVAudioPlayer?
    private var stopPlayer: AVAudioPlayer?

    private init() {
        loadSounds()
    }

    /// Hangfájlok betöltése a Bundle-ból
    private func loadSounds() {
        if let startURL = Bundle.main.url(forResource: "start_soft_click_smooth", withExtension: "wav") {
            do {
                startPlayer = try AVAudioPlayer(contentsOf: startURL)
                startPlayer?.prepareToPlay()
                print("SoundManager: Start sound loaded")
            } catch {
                print("SoundManager: Failed to load start sound: \(error)")
            }
        } else {
            print("SoundManager: Start sound file not found in bundle")
        }

        if let stopURL = Bundle.main.url(forResource: "stop_soft_click_smooth", withExtension: "wav") {
            do {
                stopPlayer = try AVAudioPlayer(contentsOf: stopURL)
                stopPlayer?.prepareToPlay()
                print("SoundManager: Stop sound loaded")
            } catch {
                print("SoundManager: Failed to load stop sound: \(error)")
            }
        } else {
            print("SoundManager: Stop sound file not found in bundle")
        }
    }

    /// Start hang lejátszása (felvétel indításakor)
    func playStart() {
        startPlayer?.currentTime = 0
        startPlayer?.play()
    }

    /// Stop hang lejátszása (felvétel leállításakor)
    func playStop() {
        stopPlayer?.currentTime = 0
        stopPlayer?.play()
    }
}
