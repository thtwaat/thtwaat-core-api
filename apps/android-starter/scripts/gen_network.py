from pathlib import Path
ROOT = Path(r"E:\THTWAAT\thtwaat-core-api\apps\android-starter")

def w(rel: str, content: str) -> None:
    path = ROOT / rel.replace("/", "\\")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.lstrip("\n"), encoding="utf-8", newline="\n")
    print("wrote", rel)

w("app/src/main/java/com/thtwaat/starter/core/network/AuthInterceptor.kt", r'''
package com.thtwaat.starter.core.network

import com.thtwaat.starter.core.datastore.SessionStore
import kotlinx.coroutines.runBlocking
import okhttp3.Interceptor
import okhttp3.Response
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthInterceptor @Inject constructor(
    private val sessionStore: SessionStore,
) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val original = chain.request()
        val token = runBlocking { sessionStore.getAccessToken() }
        val apiKey = runBlocking { sessionStore.getApiKey() }
        val builder = original.newBuilder()
        val bearer = token ?: apiKey
        if (!bearer.isNullOrBlank()) {
            builder.header("Authorization", "Bearer $bearer")
        }
        if (!apiKey.isNullOrBlank()) {
            builder.header("X-API-Key", apiKey)
        }
        builder.header("Accept", "application/json")
        return chain.proceed(builder.build())
    }
}
''')

w("app/src/main/java/com/thtwaat/starter/core/network/TokenAuthenticator.kt", r'''
package com.thtwaat.starter.core.network

import com.thtwaat.starter.core.datastore.SessionStore
import com.thtwaat.starter.data.remote.api.AuthApi
import com.thtwaat.starter.data.remote.dto.RefreshRequestDto
import kotlinx.coroutines.runBlocking
import okhttp3.Authenticator
import okhttp3.Request
import okhttp3.Response
import okhttp3.Route
import javax.inject.Inject
import javax.inject.Provider
import javax.inject.Singleton

@Singleton
class TokenAuthenticator @Inject constructor(
    private val sessionStore: SessionStore,
    private val authApiProvider: Provider<AuthApi>,
) : Authenticator {
    override fun authenticate(route: Route?, response: Response): Request? {
        if (responseCount(response) >= 2) return null
        return runBlocking {
            val refresh = sessionStore.getRefreshToken() ?: return@runBlocking null
            try {
                val tokens = authApiProvider.get().refresh(RefreshRequestDto(refresh))
                sessionStore.saveTokens(tokens.accessToken, tokens.refreshToken)
                response.request.newBuilder()
                    .header("Authorization", "Bearer ${tokens.accessToken}")
                    .build()
            } catch (_: Exception) {
                sessionStore.clearSession()
                null
            }
        }
    }

    private fun responseCount(response: Response): Int {
        var result = 1
        var prior = response.priorResponse
        while (prior != null) {
            result++
            prior = prior.priorResponse
        }
        return result
    }
}
''')

w("app/src/main/java/com/thtwaat/starter/core/network/SseClient.kt", r'''
package com.thtwaat.starter.core.network

import com.thtwaat.starter.BuildConfig
import com.thtwaat.starter.core.datastore.SessionStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.isActive
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import javax.inject.Inject
import javax.inject.Singleton
import kotlin.coroutines.coroutineContext

data class SseEvent(val event: String, val data: String) {
    fun asJson(json: Json = Json { ignoreUnknownKeys = true }): JsonObject? = try {
        json.parseToJsonElement(data).jsonObject
    } catch (_: Exception) {
        null
    }
}

@Singleton
class SseClient @Inject constructor(
    private val okHttpClient: OkHttpClient,
    private val sessionStore: SessionStore,
) {
    fun streamPost(path: String, jsonBody: String): Flow<SseEvent> = flow {
        val token = sessionStore.getAccessToken()
        val apiKey = sessionStore.getApiKey()
        val url = BuildConfig.API_BASE_URL.trimEnd('/') + path
        val builder = Request.Builder()
            .url(url)
            .post(jsonBody.toRequestBody("application/json".toMediaType()))
            .header("Accept", "text/event-stream")
            .header("Content-Type", "application/json")
        val bearer = token ?: apiKey
        if (!bearer.isNullOrBlank()) builder.header("Authorization", "Bearer $bearer")
        if (!apiKey.isNullOrBlank()) builder.header("X-API-Key", apiKey)

        okHttpClient.newCall(builder.build()).execute().use { response ->
            if (!response.isSuccessful) {
                throw ApiException("SSE failed: ${response.code}", status = response.code)
            }
            val source = response.body?.source() ?: return@use
            var event = "message"
            val data = StringBuilder()
            while (coroutineContext.isActive && !source.exhausted()) {
                val line = source.readUtf8Line() ?: break
                when {
                    line.isEmpty() -> {
                        if (data.isNotEmpty()) {
                            emit(SseEvent(event, data.toString()))
                            data.clear()
                            event = "message"
                        }
                    }
                    line.startsWith(":") -> Unit
                    line.startsWith("event:") -> event = line.removePrefix("event:").trim()
                    line.startsWith("data:") -> {
                        if (data.isNotEmpty()) data.append('\n')
                        data.append(line.removePrefix("data:").trimStart())
                    }
                }
            }
            if (data.isNotEmpty()) emit(SseEvent(event, data.toString()))
        }
    }.flowOn(Dispatchers.IO)

    fun extractText(event: SseEvent): String? {
        val obj = event.asJson() ?: return null
        return obj["text"]?.jsonPrimitive?.content
            ?: obj["reply"]?.jsonPrimitive?.content
            ?: obj["token"]?.jsonPrimitive?.content
    }
}
''')

w("app/src/main/java/com/thtwaat/starter/di/AppModule.kt", r'''
package com.thtwaat.starter.di

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.preferencesDataStore
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

private val Context.dataStore by preferencesDataStore(name = "thtwaat_session")

@Module
@InstallIn(SingletonComponent::class)
object AppModule {
    @Provides
    @Singleton
    fun provideDataStore(@ApplicationContext context: Context): DataStore<Preferences> =
        context.dataStore
}
''')

w("app/src/main/java/com/thtwaat/starter/di/NetworkModule.kt", r'''
package com.thtwaat.starter.di

import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import com.thtwaat.starter.BuildConfig
import com.thtwaat.starter.core.network.AuthInterceptor
import com.thtwaat.starter.core.network.TokenAuthenticator
import com.thtwaat.starter.data.remote.api.AgentsApi
import com.thtwaat.starter.data.remote.api.AnalyticsApi
import com.thtwaat.starter.data.remote.api.AuthApi
import com.thtwaat.starter.data.remote.api.BillingApi
import com.thtwaat.starter.data.remote.api.ChatApi
import com.thtwaat.starter.data.remote.api.DomainsApi
import com.thtwaat.starter.data.remote.api.KnowledgeApi
import com.thtwaat.starter.data.remote.api.MarketplaceApi
import com.thtwaat.starter.data.remote.api.ProductGeneratorApi
import com.thtwaat.starter.data.remote.api.UsageApi
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import java.util.concurrent.TimeUnit
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {
    @Provides
    @Singleton
    fun provideJson(): Json = Json {
        ignoreUnknownKeys = true
        isLenient = true
        encodeDefaults = true
    }

    @Provides
    @Singleton
    fun provideOkHttp(
        authInterceptor: AuthInterceptor,
        authenticator: TokenAuthenticator,
    ): OkHttpClient {
        val logging = HttpLoggingInterceptor().apply {
            level = if (BuildConfig.DEBUG) HttpLoggingInterceptor.Level.BASIC else HttpLoggingInterceptor.Level.NONE
        }
        return OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(90, TimeUnit.SECONDS)
            .writeTimeout(90, TimeUnit.SECONDS)
            .addInterceptor(authInterceptor)
            .authenticator(authenticator)
            .addInterceptor(logging)
            .build()
    }

    @Provides
    @Singleton
    fun provideRetrofit(client: OkHttpClient, json: Json): Retrofit {
        val contentType = "application/json".toMediaType()
        return Retrofit.Builder()
            .baseUrl(BuildConfig.API_BASE_URL.trimEnd('/') + "/")
            .client(client)
            .addConverterFactory(json.asConverterFactory(contentType))
            .build()
    }

    @Provides @Singleton fun authApi(r: Retrofit): AuthApi = r.create(AuthApi::class.java)
    @Provides @Singleton fun chatApi(r: Retrofit): ChatApi = r.create(ChatApi::class.java)
    @Provides @Singleton fun knowledgeApi(r: Retrofit): KnowledgeApi = r.create(KnowledgeApi::class.java)
    @Provides @Singleton fun agentsApi(r: Retrofit): AgentsApi = r.create(AgentsApi::class.java)
    @Provides @Singleton fun marketplaceApi(r: Retrofit): MarketplaceApi = r.create(MarketplaceApi::class.java)
    @Provides @Singleton fun productApi(r: Retrofit): ProductGeneratorApi = r.create(ProductGeneratorApi::class.java)
    @Provides @Singleton fun domainsApi(r: Retrofit): DomainsApi = r.create(DomainsApi::class.java)
    @Provides @Singleton fun usageApi(r: Retrofit): UsageApi = r.create(UsageApi::class.java)
    @Provides @Singleton fun billingApi(r: Retrofit): BillingApi = r.create(BillingApi::class.java)
    @Provides @Singleton fun analyticsApi(r: Retrofit): AnalyticsApi = r.create(AnalyticsApi::class.java)
}
''')

print("network+di done")
