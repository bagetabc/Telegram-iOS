import SwiftUI

@main
struct DearTGApp: App {
    @StateObject private var session = DearTGSession()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(session)
                .preferredColorScheme(.dark)
        }
    }
}
