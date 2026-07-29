from pathlib import Path
ROOT = Path(r"E:\THTWAAT\thtwaat-core-api\apps\android-starter")

def w(rel: str, content: str) -> None:
    path = ROOT / rel.replace("/", "\\")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.lstrip("\n"), encoding="utf-8", newline="\n")
    print("wrote", rel)

w("app/src/main/res/drawable/ic_launcher_foreground.xml", r'''
<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp"
    android:height="108dp"
    android:viewportWidth="108"
    android:viewportHeight="108">
    <path
        android:fillColor="#FFFFFF"
        android:pathData="M30,54c0,-13.2 10.8,-24 24,-24s24,10.8 24,24 -10.8,24 -24,24 -24,-10.8 -24,-24z"/>
    <path
        android:fillColor="#0F766E"
        android:pathData="M44,46h20v4h-20zM44,54h14v4h-14z"/>
</vector>
''')

w("app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml", r'''
<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@color/ic_launcher_background"/>
    <foreground android:drawable="@drawable/ic_launcher_foreground"/>
</adaptive-icon>
''')

w("app/src/test/java/com/thtwaat/starter/AuthRepositoryTest.kt", r'''
package com.thtwaat.starter

import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import com.thtwaat.starter.core.datastore.SessionStore
import com.thtwaat.starter.core.util.Result
import com.thtwaat.starter.data.remote.api.AuthApi
import com.thtwaat.starter.data.repository.AuthRepository
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import retrofit2.Retrofit

class AuthRepositoryTest {
    private lateinit var server: MockWebServer
    private lateinit var api: AuthApi
    private val sessionStore = mockk<SessionStore>(relaxed = true)

    @Before
    fun setup() {
        server = MockWebServer()
        server.start()
        val json = Json { ignoreUnknownKeys = true }
        api = Retrofit.Builder()
            .baseUrl(server.url("/"))
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
            .create(AuthApi::class.java)
    }

    @After
    fun tearDown() {
        server.shutdown()
    }

    @Test
    fun loginStoresTokens() = runTest {
        server.enqueue(
            MockResponse().setBody(
                """{"access_token":"acc","refresh_token":"ref","token_type":"bearer","expires_in":3600}""",
            ),
        )
        val repo = AuthRepository(api, sessionStore)
        val result = repo.login("a@b.com", "secret")
        assertTrue(result is Result.Success)
        assertEquals("acc", (result as Result.Success).data.accessToken)
        coVerify { sessionStore.saveTokens("acc", "ref") }
    }

    @Test
    fun loginHttpErrorMaps() = runTest {
        server.enqueue(MockResponse().setResponseCode(401).setBody("""{"detail":"Unauthorized"}"""))
        val repo = AuthRepository(api, sessionStore)
        val result = repo.login("a@b.com", "bad")
        assertTrue(result is Result.Error)
        assertEquals(401, (result as Result.Error).status)
    }
}
''')

w("app/src/androidTest/java/com/thtwaat/starter/LoginScreenSmokeTest.kt", r'''
package com.thtwaat.starter

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
import org.junit.Rule
import org.junit.Test

class LoginScreenSmokeTest {
    @get:Rule
    val rule = createAndroidComposeRule<MainActivity>()

    @Test
    fun showsBrandOnLaunch() {
        rule.onNodeWithText("THTWAAT").assertIsDisplayed()
    }
}
''')

w("README.md", r'''
# THTWAAT Android Starter

Official Android starter app for the THTWAAT AI Platform.

Stack: Kotlin · Jetpack Compose · Material 3 · Navigation · Hilt · Retrofit · OkHttp · Kotlinx Serialization · Coil · DataStore · Coroutines/Flow

## Features

- JWT login / signup / forgot password / refresh / persistent session / logout
- Home dashboard (conversations, agents, usage, analytics)
- Streaming AI chat with suggested prompts, retry, stop, typing indicator, markdown-ish rendering
- Knowledge bases, search, upload, delete
- Agents: create, publish, API keys, widget
- Marketplace: browse, install, connect, publish, update, rollback, uninstall
- Product generator wizard (analyze → generate → publish)
- Domains: add, verify, SSL, retry
- Billing: plans, invoices, usage/quota
- Settings: profile, company, theme, API keys

Architecture: MVVM + Repository + Clean layers, offline cache for recent conversations/agents.

## Setup

1. Open `apps/android-starter` in Android Studio (Ladybug+ / AGP 8.7).
2. Copy `local.properties.example` → `local.properties` (already generated locally if SDK is present).
3. Set:

```
sdk.dir=C:\\Users\\YOU\\AppData\\Local\\Android\\Sdk
API_BASE_URL=http://10.0.2.2:8000
```

Emulator uses `10.0.2.2` for host localhost. Physical device: use your LAN IP.

## Build

```bash
cd apps/android-starter
./gradlew.bat assembleDebug
./gradlew.bat test
./gradlew.bat assembleRelease
```

## Package

`com.thtwaat.starter`

## API contract

Consumes existing backend routes only (same surface as Flutter SDK). No backend changes required.

## Notes

- Auth tokens persist in DataStore.
- OkHttp Authenticator refreshes JWT on 401.
- Chat streaming uses SSE over `POST /public/v1/chat/stream`.
''')

print("tests+readme+icon done")
