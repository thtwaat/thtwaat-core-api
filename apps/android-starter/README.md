# THTWAAT Android Starter

Production-oriented Kotlin starter app for the THTWAAT Core API. Mirrors the Flutter SDK: auth, chat (SSE streaming), knowledge, agents, marketplace, product generator, domains, usage/billing, and analytics.

## Requirements

- Android Studio Ladybug (2024.2+) or newer
- JDK 17+
- Android SDK 35
- Running THTWAAT API backend

## Setup

1. Ensure `local.properties` exists (gitignored):

   ```properties
   sdk.dir=C\:\\Users\\YOU\\AppData\\Local\\Android\\Sdk
   API_BASE_URL=http://10.0.2.2:8000
   ```

   - Emulator → host: `http://10.0.2.2:8000`
   - Physical device: `http://<lan-ip>:8000`

2. Open `apps/android-starter` in Android Studio and sync Gradle.

3. Run the **app** configuration.

## Build

```bash
cd apps/android-starter
./gradlew assembleDebug      # Windows: gradlew.bat
./gradlew test
./gradlew connectedDebugAndroidTest
```

Release builds use R8 (`minifyEnabled true`).

## API base URL

`API_BASE_URL` in `local.properties` is injected as `BuildConfig.API_BASE_URL` at configure time.

## Architecture

```
com.thtwaat.starter/
├── core/              SessionStore, AuthInterceptor, TokenAuthenticator, SseClient, safeApiCall
├── data/
│   ├── local/         Room (ConversationEntity, AgentEntity)
│   ├── remote/        Retrofit APIs + kotlinx.serialization DTOs (@SerialName snake_case)
│   └── repository/    AuthRepository, ChatRepository, FeatureRepositories, …
├── di/                AppModule, NetworkModule, RepositoryModule
└── ui/                Compose Material 3 screens + ViewModels + ThtwaatNavHost
    ├── auth/          Login, Signup, Forgot password
    ├── chat/          Streaming chat, stop/retry, suggested prompts, MarkdownText
    ├── home/          Dashboard
    ├── agents/        List, create, publish, API keys
    ├── marketplace/   Templates, install
    ├── productgenerator/
    ├── knowledge/     Bases, search, upload
    ├── domains/
    ├── billing/
    └── settings/      Profile, theme, API key, logout
```

**Stack:** MVVM · Hilt · Retrofit · OkHttp · kotlinx.serialization · DataStore · Room · Navigation Compose

## Navigation

Authenticated bottom bar: **Home · Chat · Agents · Marketplace · Settings**. Home links to Knowledge, Product generator, Domains, and Billing.

## Tests

| File | Purpose |
|------|---------|
| `app/src/test/.../AuthRepositoryTest.kt` | MockWebServer login + token persistence |
| `app/src/androidTest/.../LoginScreenSmokeTest.kt` | Compose smoke test |

## Package

`com.thtwaat.starter` — Kotlin only.
