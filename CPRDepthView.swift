//
//  CPRDepthView.swift
//  ─────────────────────────────────────────────────────────────────────────
//  Native iPhone LiDAR CPR depth tracker for the MLS Virtual Hospital.
//
//  HONESTY NOTE: this file was written without access to Xcode, a Mac, or
//  a physical iPhone — it has not been compiled or run. It is written
//  carefully against Apple's real ARKit/ARSCNView APIs as documented, but
//  treat it as a strong first draft needing real on-device debugging, not
//  verified working code. Likely rough edges: exact depth-buffer pixel
//  format handling, coordinate-space conversion, and frame-rate tuning will
//  all need adjustment once you can see it running against a manikin.
//
//  WHAT IT DOES
//  1. Opens the rear camera with ARKit's scene-depth feature (requires a
//     LiDAR-equipped iPhone — 12 Pro and later Pro/Pro Max models).
//  2. Reads the depth map at the center of frame (where the manikin's
//     chest should be, per README.md placement guidance) each frame.
//  3. Tracks that surface distance over time, detects compression cycles
//     (distance decreases then returns toward baseline = one compression),
//     and computes approximate depth (cm) and rate (/min).
//  4. Posts each completed compression as one row directly to a Supabase
//     table via REST — no custom server needed, same pattern the rest of
//     the hospital app already uses.
//
//  SETUP (see README.md for full steps)
//  - New Xcode project -> App -> SwiftUI interface, iOS 16+ target.
//  - Add "Privacy - Camera Usage Description" to Info.plist.
//  - Paste this file in, set SUPABASE_URL / SUPABASE_ANON_KEY below.
//  - Build to a real LiDAR-equipped iPhone (ARKit scene depth does not
//    work in the Simulator).
//

import SwiftUI
import ARKit
import RealityKit

// MARK: - Configuration — fill these in from your Supabase project settings.
enum SupabaseConfig {
    static let url = "https://YOUR_PROJECT.supabase.co"
    static let anonKey = "YOUR_SUPABASE_ANON_KEY"
}

// MARK: - Session pairing
// The Streamlit CPR trainer generates a short session code; the student
// types the same code into this app so the compression stream lands in the
// right browser session. Kept as a simple free-text field for now.
final class SessionState: ObservableObject {
    @Published var sessionCode: String = ""
    @Published var isStreaming: Bool = false
    @Published var lastDepthCm: Double = 0
    @Published var lastRate: Double = 0
    @Published var compressionCount: Int = 0
    @Published var statusMessage: String = "Enter session code and tap Start"
}

// MARK: - Main SwiftUI view
struct CPRDepthView: View {
    @StateObject private var session = SessionState()

    var body: some View {
        ZStack {
            ARDepthViewRepresentable(session: session)
                .ignoresSafeArea()

            VStack {
                HStack(spacing: 20) {
                    VStack {
                        Text("Depth").font(.caption).foregroundColor(.white.opacity(0.7))
                        Text(String(format: "%.1f cm", session.lastDepthCm))
                            .font(.title2).bold()
                            .foregroundColor(depthColor(session.lastDepthCm))
                    }
                    VStack {
                        Text("Rate").font(.caption).foregroundColor(.white.opacity(0.7))
                        Text(String(format: "%.0f /min", session.lastRate))
                            .font(.title2).bold()
                            .foregroundColor(rateColor(session.lastRate))
                    }
                    VStack {
                        Text("Count").font(.caption).foregroundColor(.white.opacity(0.7))
                        Text("\(session.compressionCount)")
                            .font(.title2).bold().foregroundColor(.white)
                    }
                }
                .padding()
                .background(Color.black.opacity(0.6))
                .cornerRadius(14)
                .padding(.top, 50)

                Spacer()

                Circle()
                    .stroke(Color.red.opacity(0.7), lineWidth: 3)
                    .frame(width: 120, height: 120)

                Spacer()

                VStack(spacing: 12) {
                    Text(session.statusMessage)
                        .font(.caption)
                        .foregroundColor(.white)
                        .padding(.horizontal)

                    if !session.isStreaming {
                        TextField("Session code from the app", text: $session.sessionCode)
                            .textFieldStyle(.roundedBorder)
                            .autocapitalization(.allCharacters)
                            .padding(.horizontal, 40)
                    }

                    Button(session.isStreaming ? "Stop" : "Start Tracking") {
                        session.isStreaming.toggle()
                        session.statusMessage = session.isStreaming
                            ? "Tracking — align chest inside the red circle"
                            : "Stopped"
                    }
                    .disabled(session.sessionCode.isEmpty && !session.isStreaming)
                    .padding(.horizontal, 40)
                    .padding(.vertical, 12)
                    .background(session.isStreaming ? Color.red : Color.blue)
                    .foregroundColor(.white)
                    .cornerRadius(10)
                }
                .padding(.bottom, 40)
            }
        }
    }

    func depthColor(_ cm: Double) -> Color {
        if cm >= 5.0 && cm <= 6.0 { return .green }
        if cm > 0 { return .orange }
        return .white
    }
    func rateColor(_ rate: Double) -> Color {
        if rate >= 100 && rate <= 120 { return .green }
        if rate > 0 { return .orange }
        return .white
    }
}

// MARK: - UIViewRepresentable wrapping ARSCNView + depth processing
struct ARDepthViewRepresentable: UIViewRepresentable {
    @ObservedObject var session: SessionState

    func makeCoordinator() -> Coordinator {
        Coordinator(session: session)
    }

    func makeUIView(context: Context) -> ARSCNView {
        let view = ARSCNView(frame: .zero)
        view.session.delegate = context.coordinator
        context.coordinator.arView = view

        let config = ARWorldTrackingConfiguration()
        if ARWorldTrackingConfiguration.supportsFrameSemantics(.sceneDepth) {
            config.frameSemantics.insert(.sceneDepth)
        } else {
            session.statusMessage = "This device has no LiDAR sensor - depth unavailable."
        }
        view.session.run(config)
        return view
    }

    func updateUIView(_ uiView: ARSCNView, context: Context) {}

    final class Coordinator: NSObject, ARSessionDelegate {
        let session: SessionState
        weak var arView: ARSCNView?

        private var baselineDistance: Float?
        private var lastDistance: Float?
        private var goingDown = false
        private var minDistanceThisRep: Float = .greatestFiniteMagnitude
        private var lastCompressionTime: TimeInterval = 0
        private var recentRates: [Double] = []
        private var lastPostTime: TimeInterval = 0

        init(session: SessionState) {
            self.session = session
        }

        func session(_ session: ARSession, didUpdate frame: ARFrame) {
            guard self.session.isStreaming else { return }
            guard let depthData = frame.sceneDepth else { return }

            let distance = centerDepth(depthData.depthMap)
            guard distance.isFinite, distance > 0 else { return }

            processDistance(distance, timestamp: frame.timestamp)
        }

        // Reads the depth value at the center pixel of the depth buffer -
        // this is where the on-screen red-circle target sits, i.e. where
        // the student should have positioned the manikin's chest.
        private func centerDepth(_ depthMap: CVPixelBuffer) -> Float {
            CVPixelBufferLockBaseAddress(depthMap, .readOnly)
            defer { CVPixelBufferUnlockBaseAddress(depthMap, .readOnly) }

            let width = CVPixelBufferGetWidth(depthMap)
            let height = CVPixelBufferGetHeight(depthMap)
            guard let baseAddress = CVPixelBufferGetBaseAddress(depthMap) else { return .nan }

            let bytesPerRow = CVPixelBufferGetBytesPerRow(depthMap)
            let floatBuffer = baseAddress.assumingMemoryBound(to: Float32.self)
            let x = width / 2
            let y = height / 2
            let index = y * (bytesPerRow / MemoryLayout<Float32>.size) + x
            return floatBuffer[index]
        }

        private func processDistance(_ distanceMeters: Float, timestamp: TimeInterval) {
            let distanceCm = distanceMeters * 100

            if baselineDistance == nil {
                baselineDistance = distanceCm
                lastDistance = distanceCm
                return
            }
            guard let baseline = baselineDistance, let last = lastDistance else { return }

            // Slowly drift the baseline to tolerate the phone/manikin
            // settling, so long holds don't get misread as a giant rep.
            baselineDistance = baseline * 0.995 + distanceCm * 0.005

            let movingDown = distanceCm < last - 0.15   // ~1.5mm noise floor
            let movingUp = distanceCm > last + 0.15

            if movingDown {
                goingDown = true
                minDistanceThisRep = min(minDistanceThisRep, distanceCm)
            } else if movingUp && goingDown {
                let depth = max(0, baseline - minDistanceThisRep)
                registerCompression(depthCm: Double(depth), timestamp: timestamp)
                goingDown = false
                minDistanceThisRep = .greatestFiniteMagnitude
            }

            lastDistance = distanceCm
        }

        private func registerCompression(depthCm: Double, timestamp: TimeInterval) {
            DispatchQueue.main.async {
                self.session.compressionCount += 1
                self.session.lastDepthCm = depthCm
            }

            if lastCompressionTime > 0 {
                let intervalSec = timestamp - lastCompressionTime
                if intervalSec > 0.15 && intervalSec < 3.0 {   // sane bounds: 20-400/min
                    let rate = 60.0 / intervalSec
                    recentRates.append(rate)
                    if recentRates.count > 5 { recentRates.removeFirst() }
                    let avgRate = recentRates.reduce(0, +) / Double(recentRates.count)
                    DispatchQueue.main.async { self.session.lastRate = avgRate }
                }
            }
            lastCompressionTime = timestamp

            // Throttle network posts to at most ~4/sec even under fast compressions.
            if timestamp - lastPostTime > 0.25 {
                lastPostTime = timestamp
                postCompression(depthCm: depthCm, rate: recentRates.last ?? 0)
            }
        }

        private func postCompression(depthCm: Double, rate: Double) {
            guard !session.sessionCode.isEmpty else { return }
            guard let url = URL(string: "\(SupabaseConfig.url)/rest/v1/vh_cpr_depth_stream") else { return }

            var request = URLRequest(url: url)
            request.httpMethod = "POST"
            request.setValue(SupabaseConfig.anonKey, forHTTPHeaderField: "apikey")
            request.setValue("Bearer \(SupabaseConfig.anonKey)", forHTTPHeaderField: "Authorization")
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")

            let body: [String: Any] = [
                "session_code": session.sessionCode,
                "depth_cm": depthCm,
                "rate_per_min": rate,
                "device_model": UIDevice.current.model,
            ]
            request.httpBody = try? JSONSerialization.data(withJSONObject: body)

            URLSession.shared.dataTask(with: request) { _, response, error in
                if let error = error {
                    DispatchQueue.main.async {
                        self.session.statusMessage = "Network error: \(error.localizedDescription)"
                    }
                }
            }.resume()
        }
    }
}
