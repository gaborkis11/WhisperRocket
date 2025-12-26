//
//  ProcessingView.swift
//  WhisperRocket
//
//  Created by Gabor Kis on 2025. 12. 26..
//

import SwiftUI
import Combine

/// Csillag adat
struct Star: Identifiable {
    let id = UUID()
    var x: CGFloat
    var y: CGFloat
    var size: CGFloat
    var speed: CGFloat
}

/// Processing nézet - rakéta animáció + csillagok + vicces üzenetek
struct ProcessingView: View {
    // Csillagok
    @State private var stars: [Star] = []

    // Animáció frame
    @State private var animationFrame: Int = 0

    // Aktuális üzenet
    @State private var currentMessage: String = ""

    // Vicces üzenetek
    private let messages = [
        "Transcribing your thoughts...",
        "Converting speech to text...",
        "Processing your words...",
        "Almost there...",
        "Just a moment...",
        "Making your cocktail...",
        "Brewing some magic...",
        "Cooking up your text...",
        "Summoning the words...",
        "Decoding your genius...",
        "Translating brilliance...",
        "Working overtime here...",
        "Hold my coffee...",
        "Doing the heavy lifting...",
        "Crunching the soundwaves...",
        "Teaching AI to listen...",
        "One moment of magic...",
        "Converting genius to text...",
        "Whisper is thinking...",
        "Interpreting your wisdom...",
        "Almost got it...",
        "Patience, young padawan...",
        "Loading awesomeness...",
        "Shazam! Almost ready...",
        "BRB, transcribing..."
    ]

    // Timer-ek
    private let animationTimer = Timer.publish(every: 1.0/30.0, on: .main, in: .common).autoconnect()
    private let messageTimer = Timer.publish(every: 2, on: .main, in: .common).autoconnect()

    var body: some View {
        ZStack {
            Canvas { context, size in
                // Csillagok rajzolása
                drawStars(context: context, size: size)

                // Rakéta középen
                let rocketX = size.width / 2 + 15
                let rocketY: CGFloat = 38
                drawRocket(context: context, x: rocketX, y: rocketY)
            }

            // Vicces szöveg alul
            VStack {
                Spacer()
                Text(currentMessage)
                    .font(.system(size: 10).italic())
                    .foregroundColor(Color(white: 0.78))
                    .padding(.bottom, 12)
            }
        }
        .onAppear {
            initStars()
            currentMessage = messages.randomElement() ?? messages[0]
        }
        .onReceive(animationTimer) { _ in
            updateStars()
            animationFrame = (animationFrame + 1) % 60
        }
        .onReceive(messageTimer) { _ in
            currentMessage = messages.randomElement() ?? messages[0]
        }
    }

    /// Csillagok inicializálása
    private func initStars() {
        stars = (0..<15).map { _ in
            Star(
                x: CGFloat.random(in: 0...350),
                y: CGFloat.random(in: 10...55),
                size: CGFloat.random(in: 1.5...3.5),
                speed: CGFloat.random(in: 2...5)
            )
        }
    }

    /// Csillagok frissítése (balra mozgás)
    private func updateStars() {
        for i in stars.indices {
            stars[i].x -= stars[i].speed
            // Ha kilép bal oldalon, újra jobb oldalon
            if stars[i].x < -5 {
                stars[i].x = 355
                stars[i].y = CGFloat.random(in: 10...55)
                stars[i].size = CGFloat.random(in: 1.5...3.5)
                stars[i].speed = CGFloat.random(in: 2...5)
            }
        }
    }

    /// Csillagok rajzolása
    private func drawStars(context: GraphicsContext, size: CGSize) {
        for star in stars {
            // Gyorsabb csillagok fényesebbek
            let brightness = 0.4 + star.speed * 0.12
            let color = Color(white: brightness).opacity(0.8)

            let rect = CGRect(
                x: star.x - star.size,
                y: star.y - star.size,
                width: star.size * 2,
                height: star.size * 2
            )
            let path = Circle().path(in: rect)
            context.fill(path, with: .color(color))
        }
    }

    /// Rakéta rajzolása (flat-design, jobbra néz)
    private func drawRocket(context: GraphicsContext, x: CGFloat, y: CGFloat) {
        let scale: CGFloat = 0.7

        // Láng animáció
        let flameOffset = CGFloat(animationFrame % 10)
        let flameLength = 18 + flameOffset + CGFloat.random(in: -3...3)

        // Külső láng (narancssárga)
        var outerFlame = Path()
        outerFlame.move(to: CGPoint(x: x - 20 * scale, y: y))
        outerFlame.addQuadCurve(
            to: CGPoint(x: x - (25 + flameLength) * scale, y: y),
            control: CGPoint(x: x - (20 + flameLength) * scale, y: y - 8 * scale)
        )
        outerFlame.addQuadCurve(
            to: CGPoint(x: x - 20 * scale, y: y),
            control: CGPoint(x: x - (20 + flameLength) * scale, y: y + 8 * scale)
        )
        context.fill(outerFlame, with: .color(Color(red: 1, green: 0.55, blue: 0).opacity(0.8)))

        // Belső láng (sárga)
        let innerLen = flameLength * 0.6
        var innerFlame = Path()
        innerFlame.move(to: CGPoint(x: x - 20 * scale, y: y))
        innerFlame.addQuadCurve(
            to: CGPoint(x: x - (22 + innerLen) * scale, y: y),
            control: CGPoint(x: x - (20 + innerLen) * scale, y: y - 4 * scale)
        )
        innerFlame.addQuadCurve(
            to: CGPoint(x: x - 20 * scale, y: y),
            control: CGPoint(x: x - (20 + innerLen) * scale, y: y + 4 * scale)
        )
        context.fill(innerFlame, with: .color(Color(red: 1, green: 1, blue: 0.4).opacity(0.9)))

        // Rakéta test (világosszürke)
        var body = Path()
        body.move(to: CGPoint(x: x + 30 * scale, y: y))
        body.addQuadCurve(
            to: CGPoint(x: x - 5 * scale, y: y - 12 * scale),
            control: CGPoint(x: x + 25 * scale, y: y - 12 * scale)
        )
        body.addLine(to: CGPoint(x: x - 20 * scale, y: y - 8 * scale))
        body.addLine(to: CGPoint(x: x - 20 * scale, y: y + 8 * scale))
        body.addLine(to: CGPoint(x: x - 5 * scale, y: y + 12 * scale))
        body.addQuadCurve(
            to: CGPoint(x: x + 30 * scale, y: y),
            control: CGPoint(x: x + 25 * scale, y: y + 12 * scale)
        )
        context.fill(body, with: .color(Color(red: 0.92, green: 0.92, blue: 0.94)))

        // Orrkúp (piros)
        var nose = Path()
        nose.move(to: CGPoint(x: x + 30 * scale, y: y))
        nose.addQuadCurve(
            to: CGPoint(x: x + 15 * scale, y: y - 10 * scale),
            control: CGPoint(x: x + 28 * scale, y: y - 8 * scale)
        )
        nose.addLine(to: CGPoint(x: x + 15 * scale, y: y + 10 * scale))
        nose.addQuadCurve(
            to: CGPoint(x: x + 30 * scale, y: y),
            control: CGPoint(x: x + 28 * scale, y: y + 8 * scale)
        )
        context.fill(nose, with: .color(Color(red: 0.94, green: 0.35, blue: 0.35)))

        // Felső szárny (piros)
        var topFin = Path()
        topFin.move(to: CGPoint(x: x - 10 * scale, y: y - 10 * scale))
        topFin.addLine(to: CGPoint(x: x - 20 * scale, y: y - 22 * scale))
        topFin.addLine(to: CGPoint(x: x - 22 * scale, y: y - 10 * scale))
        topFin.closeSubpath()
        context.fill(topFin, with: .color(Color(red: 0.94, green: 0.35, blue: 0.35)))

        // Alsó szárny (piros)
        var bottomFin = Path()
        bottomFin.move(to: CGPoint(x: x - 10 * scale, y: y + 10 * scale))
        bottomFin.addLine(to: CGPoint(x: x - 20 * scale, y: y + 22 * scale))
        bottomFin.addLine(to: CGPoint(x: x - 22 * scale, y: y + 10 * scale))
        bottomFin.closeSubpath()
        context.fill(bottomFin, with: .color(Color(red: 0.94, green: 0.35, blue: 0.35)))

        // Ablak (kék kör)
        let windowRect = CGRect(
            x: x + 5 * scale - 6 * scale,
            y: y - 6 * scale,
            width: 12 * scale,
            height: 12 * scale
        )
        context.fill(Circle().path(in: windowRect), with: .color(Color(red: 0.4, green: 0.7, blue: 1)))

        // Ablak fény
        let highlightRect = CGRect(
            x: x + 3 * scale - 2 * scale,
            y: y - 2 * scale - 2 * scale,
            width: 4 * scale,
            height: 4 * scale
        )
        context.fill(Circle().path(in: highlightRect), with: .color(Color(red: 0.78, green: 0.9, blue: 1)))
    }
}
