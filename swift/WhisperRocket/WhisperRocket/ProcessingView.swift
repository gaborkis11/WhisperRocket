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

/// Felúszó szavak komponens - ambient vizuális feedback a transzkripció folyamatáról
struct FloatingWordsView: View {
    let text: String

    @State private var displayedPhrase: String = ""
    @State private var opacity: Double = 0
    @State private var isAnimating: Bool = false
    @State private var offsetX: CGFloat = 0
    @State private var offsetY: CGFloat = 0
    @State private var lastShownText: String = ""

    // Timer - 2.5 másodpercenként új kifejezés
    private let wordTimer = Timer.publish(every: 2.5, on: .main, in: .common).autoconnect()

    var body: some View {
        Text(displayedPhrase.isEmpty ? "" : "\u{201E}\(displayedPhrase)\u{201D}")
            .font(.system(size: 12, design: .monospaced))
            .foregroundColor(Color(white: 0.6))
            .lineLimit(1)
            .frame(maxWidth: 110)
            .opacity(opacity)
            .offset(x: offsetX, y: offsetY)
            .animation(.easeInOut(duration: 0.5), value: opacity)
            .animation(.easeOut(duration: 0.3), value: offsetX)
            .animation(.easeOut(duration: 0.3), value: offsetY)
            .onChange(of: text) { newText in
                // Csak akkor jelenítünk meg, ha teljes szó van (szóköz, pont, vagy vessző az utolsó karakter)
                if !newText.isEmpty && !isAnimating && isCompleteWord(newText) {
                    showRandomPhrase()
                }
            }
            .onReceive(wordTimer) { _ in
                // Timer-nél is csak teljes szónál
                if !text.isEmpty && isCompleteWord(text) {
                    showRandomPhrase()
                }
            }
    }

    /// Ellenőrzi, hogy a szöveg teljes szóra végződik-e (nem félbevágott token)
    private func isCompleteWord(_ text: String) -> Bool {
        guard let lastChar = text.last else { return false }
        // Teljes szó, ha szóköz, pont, vessző, kérdőjel, felkiáltójel, vagy kettőspont az utolsó karakter
        return lastChar == " " || lastChar == "." || lastChar == "," ||
               lastChar == "?" || lastChar == "!" || lastChar == ":"
    }

    /// Random pozíció generálása - bal vagy jobb oldalon, NE középen (ahol a rakéta van)
    private func randomPosition() {
        // Popup szélesség: 350, magasság: 100
        // Rakéta + láng: kb. -60...+80 közötti x tartomány (középhez képest)
        // Szöveg max 110px széles, tehát +-55px a középpontjától
        //
        // Biztonságos zónák (padding-gel a szélektől):
        // - Bal oldal: -105 ... -75 (a szöveg bal széle: 175-105-55=15, jobb széle: 175-75+55=155 - OK)
        // - Jobb oldal: +85 ... +105 (a szöveg bal széle: 175+85-55=205, jobb széle: 175+105+55=335 - OK)
        let leftSide = Bool.random()
        if leftSide {
            offsetX = CGFloat.random(in: -105 ... -75)
        } else {
            offsetX = CGFloat.random(in: 85 ... 105)
        }
        // Függőlegesen: -15 ... +5 (ne menjen túl fel vagy le)
        offsetY = CGFloat.random(in: -15 ... 5)
    }

    /// 3-4 szavas kifejezés megjelenítése
    private func showRandomPhrase() {
        // Ha már animálunk vagy nincs szöveg, skip
        guard !isAnimating, !text.isEmpty else { return }

        // Ne mutassuk ugyanazt újra
        guard text != lastShownText else { return }

        // Szavak kinyerése - TELJES szavak (szóközzel elválasztva)
        let words = text.split(separator: " ")
            .map { String($0).trimmingCharacters(in: .punctuationCharacters) }
            .filter { $0.count >= 2 }

        guard words.count >= 2 else { return }

        // Utolsó 2-3 szó egyben (mondatrész) - rövidebb, hogy elférjen
        let phraseLength = min(Int.random(in: 2...3), words.count)
        let phraseWords = words.suffix(phraseLength)
        let phrase = phraseWords.joined(separator: " ")

        isAnimating = true
        displayedPhrase = phrase
        lastShownText = text

        // Random pozíció (bal vagy jobb oldalon)
        randomPosition()

        // Fade in
        withAnimation(.easeIn(duration: 0.5)) {
            opacity = 0.7
        }

        // Fade out 1.5s után
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
            withAnimation(.easeOut(duration: 0.5)) {
                opacity = 0
            }

            // Animáció vége
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                isAnimating = false
            }
        }
    }
}

/// Processing nézet - rakéta animáció + csillagok + felúszó szavak + vicces üzenetek
struct ProcessingView: View {
    @EnvironmentObject var controller: PopupWindowController

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
            // Felúszó szavak - HÁTTÉRBEN, a rakéta mögött
            FloatingWordsView(text: controller.partialText)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .offset(y: -5) // Kicsit feljebb, a rakéta környékén

            // Csillagok és rakéta
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
