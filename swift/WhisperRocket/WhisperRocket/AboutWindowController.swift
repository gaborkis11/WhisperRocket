//
//  AboutWindowController.swift
//  WhisperRocket
//
//  Created by Gabor Kis on 2025. 12. 27..
//

import Cocoa
import SwiftUI

/// About ablak kezelő
class AboutWindowController {
    static let shared = AboutWindowController()

    private var window: NSWindow?

    private init() {}

    /// About ablak megjelenítése
    func showAbout() {
        if window == nil {
            let view = AboutView()
            let hostingController = NSHostingController(rootView: view)

            let newWindow = NSWindow(
                contentRect: NSRect(x: 0, y: 0, width: 320, height: 340),
                styleMask: [.titled, .closable],
                backing: .buffered,
                defer: false
            )

            newWindow.contentViewController = hostingController
            newWindow.title = "About"
            newWindow.center()
            newWindow.isReleasedWhenClosed = false

            window = newWindow
        }

        window?.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }
}

/// About nézet
struct AboutView: View {
    // App verzió kiolvasása
    private var appVersion: String {
        Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0"
    }

    var body: some View {
        VStack(spacing: 12) {
            Spacer()
                .frame(height: 8)

            // App ikon (eredeti rakéta)
            Image("AboutIcon")
                .resizable()
                .aspectRatio(contentMode: .fit)
                .frame(width: 64, height: 64)

            // App név
            Text("WhisperRocket")
                .font(.title2)
                .fontWeight(.bold)

            // Verzió (zárójel nélkül)
            Text("Version \(appVersion)")
                .font(.caption)
                .foregroundColor(.secondary)

            Divider()
                .padding(.horizontal, 32)

            // Leírás
            Text("Fast, local speech-to-text for macOS")
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)

            // Powered by
            HStack(spacing: 4) {
                Text("Powered by")
                    .foregroundColor(.secondary)
                Text("Studio137")
                    .fontWeight(.medium)
            }
            .font(.caption)

            Divider()
                .padding(.horizontal, 32)

            // Fejlesztő
            VStack(spacing: 4) {
                Text("Developed by")
                    .font(.caption)
                    .foregroundColor(.secondary)
                Text("Gabor Kis")
                    .font(.subheadline)
                    .fontWeight(.medium)
            }

            // Linkek
            HStack(spacing: 16) {
                Button {
                    if let url = URL(string: "https://github.com/gaborkis11/WhisperRocket") {
                        NSWorkspace.shared.open(url)
                    }
                } label: {
                    Label("GitHub", systemImage: "link")
                }
                .buttonStyle(.link)
            }

            // Copyright
            Text("© 2025 Gabor Kis. All rights reserved.")
                .font(.caption2)
                .foregroundColor(.secondary)
                .padding(.bottom, 16)
        }
        .frame(width: 280, height: 320)
        .padding(.horizontal)
    }
}

#Preview {
    AboutView()
}
