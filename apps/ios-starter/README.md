# THTWAAT iOS Starter

Official iOS starter app for the THTWAAT AI Platform.

- Swift 6 · SwiftUI · NavigationStack · MVVM
- Combine · URLSession · Keychain · SPM
- Charts · MarkdownUI
- Zero backend changes (same API surface as Flutter / Android SDKs)

## Features

- Auth: login, signup, forgot password, JWT + refresh, Keychain, logout
- Home: dashboard, usage chart, recent agents/conversations, analytics cards
- Chat: SSE streaming, history, MarkdownUI, suggested prompts, retry, stop, typing indicator
- Knowledge: bases, upload, search, delete
- Agents: create, edit widget, publish, embed/widget, API keys
- Marketplace: browse, install, connect, publish, update, rollback, uninstall
- Product generator: analyze → generate → publish
- Domains: add, verify, SSL, retry
- Billing: plan, invoices, usage/quota
- Settings: profile, company, theme, API keys

## Requirements

- macOS 14+
- Xcode 16+ (Swift 6)
- [XcodeGen](https://github.com/yonaskolb/XcodeGen) (`brew install xcodegen`)
- Running THTWAAT API (`http://127.0.0.1:8000` for simulator)

> This package is authored on any OS; **build and archive require a Mac** with Xcode.

## Setup

```bash
cd apps/ios-starter
chmod +x scripts/generate_project.sh
./scripts/generate_project.sh
# or: xcodegen generate
open ThtwaatStarter.xcodeproj
```

Xcode resolves the **MarkdownUI** SPM dependency automatically.

### API base URL

- Debug (`Config/Debug.xcconfig`): `http://127.0.0.1:8000`
- Release (`Config/Release.xcconfig`): `https://api.thtwaat.com`

Override at runtime with env var `API_BASE_URL`.

## Architecture

```
ThtwaatStarter/
├── App/                 App entry + AppState
├── Core/
│   ├── DI/              AppDependencies
│   ├── Network/         APIClient, SSEClient
│   ├── Storage/         Keychain SessionStore
│   └── Util/            AppConfig, APIResult
├── Data/
│   ├── Models/
│   ├── Repositories/
│   └── Cache/           Offline cache (conversations/agents)
├── Features/            SwiftUI screens (MVVM)
└── Navigation/          RootView + TabView
```

## Build & test (Mac)

```bash
xcodegen generate
xcodebuild -scheme ThtwaatStarter -destination 'platform=iOS Simulator,name=iPhone 16' build
xcodebuild -scheme ThtwaatStarter -destination 'platform=iOS Simulator,name=iPhone 16' test
```

Archive for production:

```bash
xcodebuild -scheme ThtwaatStarter -configuration Release archive -archivePath build/ThtwaatStarter.xcarchive
```

## Screenshots

Place App Store captures in `Screenshots/` (see that folder’s README). Capture on Mac simulator after login against a local or staging API.

## Bundle ID

`com.thtwaat.starter`
