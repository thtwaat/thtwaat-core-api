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
