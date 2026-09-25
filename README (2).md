# iPhone LiDAR CPR Depth Tracker — Setup

**Status: written, not yet compiled or tested.** `CPRDepthView.swift` was
written without access to Xcode or a physical iPhone. Treat this as a real
first attempt at the ARKit implementation, not verified-working code —
expect to debug it on an actual LiDAR iPhone before it's reliable.

## What you need
- A Mac with Xcode installed (free from the Mac App Store)
- An Apple Developer account ($99/year) to install on a physical iPhone
  (or a free account for local testing on your own device, which works for
  personal builds but can't be distributed via TestFlight)
- An iPhone 12 Pro or newer Pro/Pro Max model (LiDAR required — regular,
  non-Pro iPhones do not have this sensor)
- Your Supabase project URL and anon (public) key

## Setup steps
1. Open Xcode → **File → New → Project → App**. Interface: **SwiftUI**.
   Minimum deployment target: **iOS 16**.
2. In the new project, delete the default `ContentView.swift` body content
   and replace the whole file's content with `CPRDepthView.swift` from
   this folder — or add `CPRDepthView.swift` as a new file and set your
   `App` struct's `WindowGroup` to show `CPRDepthView()`.
3. Open **Info.plist** (or your target's Info tab in Xcode) and add:
   - Key: `Privacy - Camera Usage Description`
   - Value: `This app uses the camera and LiDAR sensor to measure CPR compression depth during training.`
4. In `CPRDepthView.swift`, set:
   ```swift
   enum SupabaseConfig {
       static let url = "https://YOUR_PROJECT.supabase.co"
       static let anonKey = "YOUR_SUPABASE_ANON_KEY"
   }
   ```
   using the same values already in your Streamlit app's `secrets.toml`.
5. Create the Supabase table (SQL editor, once):
   ```sql
   create table vh_cpr_depth_stream (
     id            bigint generated always as identity primary key,
     session_code    text not null,
     depth_cm          double precision,
     rate_per_min        double precision,
     device_model           text,
     created_at                timestamp default now()
   );
   ```
6. Connect a real iPhone Pro/Pro Max via cable, select it as the build
   target (not a Simulator — **ARKit scene depth does not run in the
   Simulator**), and hit Run.

## Placement guidance — best-effort, unverified
I'm giving you a reasonable starting point based on how ARKit's depth
sensing generally behaves, not a measurement I've verified against a real
manikin:
- Mount the phone on a small stand or tripod, roughly **40–60 cm above the
  manikin's chest**, camera pointed straight down.
- Keep the red target circle centered on the compression point (lower
  half of the sternum).
- Avoid strong side lighting or reflective manikin surfaces — LiDAR can
  behave inconsistently on very shiny materials.
- Expect to need to tune the noise-floor and rep-detection thresholds
  (`0.15` cm in the Swift file) once you see real readings — manikin
  material and phone angle will both affect how clean the signal is.

## Known rough edges to expect
- Pixel format / stride handling in `centerDepth()` is written to Apple's
  documented `CVPixelBuffer` behavior for `sceneDepth.depthMap` (32-bit
  float, one channel) but hasn't been run against a real buffer.
- No smoothing/Kalman filtering on the raw depth signal yet — if it's too
  jumpy in practice, that's the first thing to add.
- No handling yet for the phone losing ARKit tracking mid-session (e.g. if
  it's bumped) — would show as depth suddenly jumping to nonsense values.

## How this connects to the hospital app
`medsim_cpr.py`'s `depth_hardware` tier (in the main repo) is meant to
poll the `vh_cpr_depth_stream` table for rows matching the session code
the student entered on both the phone and the browser, and render real
depth/rate feedback from that data instead of the webcam-only estimate.
That polling code is the next piece to wire up once this app is confirmed
working on a real device.
