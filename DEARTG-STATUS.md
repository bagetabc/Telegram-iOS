# DearTG development status

Branch: `deartg-dev`

## Implemented in this branch
- Independent local API foundation under `deartg-server/`: registration, login, profile, chat creation/listing, message history/sending, WebSocket message events.
- SQLite persistence and password hashing/token signing for local development.
- Windows local-run instructions.
- GitHub Actions backend validation workflow.

## Not yet implemented
- iOS UI/branding and application icon replacement.
- iOS networking integration with the DearTG API.
- Removal/replacement of Telegram MTProto authentication, contacts, chats, calls, push and other service dependencies.
- Telegram management bot (explicitly next phase after backend/client foundation).
- Production security and deployment.

The repository's upstream build instructions require macOS/Xcode and Bazel. Do not treat backend CI as an iOS app build.
