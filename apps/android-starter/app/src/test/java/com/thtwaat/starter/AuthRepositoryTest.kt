package com.thtwaat.starter

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.datastore.preferences.core.Preferences
import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import com.thtwaat.starter.core.datastore.SessionStore
import com.thtwaat.starter.core.util.Result
import com.thtwaat.starter.data.remote.api.AuthApi
import com.thtwaat.starter.data.repository.AuthRepository
import kotlinx.coroutines.Job
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import retrofit2.Retrofit

class AuthRepositoryTest {
    @get:Rule
    val tmp = TemporaryFolder()

    private lateinit var server: MockWebServer
    private lateinit var api: AuthApi
    private lateinit var sessionStore: SessionStore
    private lateinit var dataStore: DataStore<Preferences>

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

        dataStore = PreferenceDataStoreFactory.create(
            scope = kotlinx.coroutines.CoroutineScope(Job()),
            produceFile = { tmp.newFile("session.preferences_pb") },
        )
        sessionStore = SessionStore(dataStore)
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
        assertEquals("acc", sessionStore.getAccessToken())
        assertEquals("ref", sessionStore.getRefreshToken())
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
