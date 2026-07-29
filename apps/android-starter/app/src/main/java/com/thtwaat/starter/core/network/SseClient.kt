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
