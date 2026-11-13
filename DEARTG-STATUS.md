# DearTG development status

Branch: `deartg-dev`

## Implemented foundation

- A standalone native SwiftUI iOS app under `DearTG-iOS/` with a DearTG-branded login/registration screen, server address setting, chat list, chat creation, conversation view, and member invitation.
- A locally hosted FastAPI backend under `deartg-server/` with username/password registration and login, profiles, chat membership, message history/sending, and WebSocket message events.
- SQLite persistence, PBKDF2-HMAC-SHA256 password hashing, signed expiring bearer tokens, and API integration tests.
- A generated DearTG app icon and a GitHub Actions iOS Simulator build workflow.
- A GitHub Actions backend validation workflow.
- DearTG display name and URL scheme changes in the upstream iOS build configuration.
- The old upstream Telegram release workflow has been removed from this branch so it cannot accidentally publish a Telegram-branded build as DearTG.

## Current limitations — not a finished messenger yet

- The SwiftUI client is a separate MVP target; it does not replace the upstream Telegram app target or all of its source code.
- The current account model is username/password, not phone/SMS verification.
- The client currently polls for chats/messages; WebSocket push is present in the backend but not yet wired into the iOS client.
- No media uploads, voice/video calls, APNs push notifications, end-to-end encryption, account recovery, moderation tools, or production deployment.
- No DearTG management bot yet. Bot development starts after the iOS/backend foundation has a passing build and test run.
- No TON wallet, real TON transfers, Telegram Stars, Telegram collectible usernames, or Telegram NFT issuance. Those require separate wallet/provider integrations and verified ownership; any in-app points or gifts would be DearTG-native assets, not Telegram assets.
- The local API is for trusted LAN development only. Do not expose it to the public internet until TLS, rate limiting, token revocation/refresh, migrations, backups, abuse controls, and a reviewed security model are added.

## Build and test

- iOS: `.github/workflows/deartg-ios.yml` builds the native DearTG Simulator app on GitHub-hosted macOS.
- Backend: `.github/workflows/deartg-backend.yml` installs dependencies, compiles Python sources, runs pytest integration tests, and checks route registration.
- A successful Simulator build is not an installable signed IPA. Distribution to a physical iPhone requires Apple signing/provisioning.
