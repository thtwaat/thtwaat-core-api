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
