//
//  EqualizerView.swift
//  WhisperRocket
//
//  Created by Gabor Kis on 2025. 12. 26..
//

import SwiftUI
import Combine

/// Canvas alapú equalizer vizualizáció
struct EqualizerView: View {
    @EnvironmentObject var controller: PopupWindowController

    // Paraméterek (Python-ból átvéve)
    private let barCount = 45
    private let barWidth: CGFloat = 3
    private let barGap: CGFloat = 3
    private let maxHalfHeight: CGFloat = 25

    // Simított érték state
    @State private var smoothedAmplitude: Float = 0
    @State private var barHeights: [CGFloat] = Array(repeating: 2, count: 45)

    // Simítás - gyors attack, azonnali release
    private let attackFactor: Float = 0.6   // Gyors felfutás
    private let releaseFactor: Float = 0.8  // Azonnali visszaesés

    // Timer a frissítéshez
    private let timer = Timer.publish(every: 1.0/30.0, on: .main, in: .common).autoconnect()

    // Gauss súlyok előre kiszámítva
    private var barWeights: [CGFloat] {
        let center = CGFloat(barCount) / 2
        let sigma = CGFloat(barCount) / 4
        return (0..<barCount).map { i in
            let distance = abs(CGFloat(i) - center)
            return exp(-(distance * distance) / (2 * sigma * sigma))
        }
    }

    var body: some View {
        Canvas { context, size in
            let totalWidth = CGFloat(barCount) * (barWidth + barGap)
            let startX = (size.width - totalWidth) / 2
            let centerY = size.height / 2

            for i in 0..<barCount {
                let halfHeight = barHeights[i]
                let x = startX + CGFloat(i) * (barWidth + barGap)

                // Felső fél
                let topRect = CGRect(
                    x: x,
                    y: centerY - halfHeight,
                    width: barWidth,
                    height: halfHeight
                )
                let topPath = RoundedRectangle(cornerRadius: 1.5)
                    .path(in: topRect)
                context.fill(topPath, with: .color(.white))

                // Alsó fél
                let bottomRect = CGRect(
                    x: x,
                    y: centerY,
                    width: barWidth,
                    height: halfHeight
                )
                let bottomPath = RoundedRectangle(cornerRadius: 1.5)
                    .path(in: bottomRect)
                context.fill(bottomPath, with: .color(.white))
            }
        }
        .onReceive(timer) { _ in
            updateBars()
        }
    }

    private func updateBars() {
        // Amplitúdó közvetlenül a controller-ből
        let amplitude = controller.currentAmplitude

        // Noise gate - háttérzaj kiszűrése (0.25 alatt csend)
        let noiseThreshold: Float = 0.25
        let gatedAmplitude = amplitude > noiseThreshold ? (amplitude - noiseThreshold) / (1.0 - noiseThreshold) : 0

        // DEBUG - uncomment to see values
        // print("Amp: \(String(format: "%.3f", amplitude)) | Gated: \(String(format: "%.3f", gatedAmplitude))")

        // Ha nincs hang, azonnal 0 - ha van, minimális simítás
        if gatedAmplitude == 0 {
            smoothedAmplitude = 0
        } else {
            // Minimális simítás csak felfutáskor
            smoothedAmplitude = gatedAmplitude > smoothedAmplitude
                ? smoothedAmplitude * 0.3 + gatedAmplitude * 0.7  // attack
                : gatedAmplitude  // release: azonnal követi
        }

        // Nyers érték használata - nincs felnagyítás
        let normalizedAmp = CGFloat(smoothedAmplitude)

        // Oszlopok frissítése
        var newHeights: [CGFloat] = []
        for i in 0..<barCount {
            let weight = barWeights[i]
            // Kis random variáció csak ha van jel
            let randomFactor = normalizedAmp > 0.05 ? CGFloat.random(in: 0.9...1.1) : 1.0
            let halfHeight = max(2, normalizedAmp * maxHalfHeight * weight * randomFactor)
            newHeights.append(halfHeight)
        }
        barHeights = newHeights
    }
}

/// Kisimult equalizer (Done állapothoz)
struct FlatEqualizerView: View {
    private let barCount = 20
    private let barWidth: CGFloat = 3
    private let barGap: CGFloat = 3
    private let barHeight: CGFloat = 3

    var body: some View {
        Canvas { context, size in
            let totalWidth = CGFloat(barCount) * (barWidth + barGap)
            let startX = (size.width - totalWidth) / 2
            let centerY = size.height / 2

            for i in 0..<barCount {
                let x = startX + CGFloat(i) * (barWidth + barGap)

                // Felső fél
                let topRect = CGRect(
                    x: x,
                    y: centerY - barHeight,
                    width: barWidth,
                    height: barHeight
                )
                let topPath = RoundedRectangle(cornerRadius: 1)
                    .path(in: topRect)
                context.fill(topPath, with: .color(Color(white: 0.4)))

                // Alsó fél
                let bottomRect = CGRect(
                    x: x,
                    y: centerY,
                    width: barWidth,
                    height: barHeight
                )
                let bottomPath = RoundedRectangle(cornerRadius: 1)
                    .path(in: bottomRect)
                context.fill(bottomPath, with: .color(Color(white: 0.4)))
            }
        }
    }
}
