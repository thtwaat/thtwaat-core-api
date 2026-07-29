package com.thtwaat.starter.data.repository

import com.thtwaat.starter.core.datastore.SessionStore
import com.thtwaat.starter.core.network.safeApiCall
import com.thtwaat.starter.core.util.Result
import com.thtwaat.starter.data.remote.api.AuthApi
import com.thtwaat.starter.data.remote.dto.ForgotPasswordRequestDto
import com.thtwaat.starter.data.remote.dto.LoginRequestDto
import com.thtwaat.starter.data.remote.dto.LogoutRequestDto
import com.thtwaat.starter.data.remote.dto.ResetPasswordRequestDto
import com.thtwaat.starter.data.remote.dto.SignupRequestDto
import com.thtwaat.starter.data.remote.dto.TokenResponseDto
import com.thtwaat.starter.data.remote.dto.UserProfileDto
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthRepository @Inject constructor(
    private val api: AuthApi,
    private val sessionStore: SessionStore,
) {
    val isLoggedIn: Flow<Boolean> = sessionStore.accessToken.map { !it.isNullOrBlank() }

    suspend fun login(email: String, password: String): Result<TokenResponseDto> {
        val result = safeApiCall { api.login(LoginRequestDto(email, password)) }
        if (result is Result.Success) {
            sessionStore.saveTokens(result.data.accessToken, result.data.refreshToken)
        }
        return result
    }

    suspend fun signup(
        email: String,
        password: String,
        firstName: String,
        lastName: String,
        companyId: String? = null,
    ): Result<UserProfileDto> = safeApiCall {
        api.signup(SignupRequestDto(email, password, firstName, lastName, companyId))
    }

    suspend fun forgotPassword(email: String): Result<Unit> =
        safeApiCall { api.forgotPassword(ForgotPasswordRequestDto(email)) }

    suspend fun resetPassword(email: String, code: String, newPassword: String): Result<Unit> =
        safeApiCall { api.resetPassword(ResetPasswordRequestDto(email, code, newPassword)) }

    suspend fun me(): Result<UserProfileDto> = safeApiCall { api.me() }

    suspend fun logout(): Result<Unit> {
        val refresh = sessionStore.getRefreshToken()
        val result = if (refresh.isNullOrBlank()) {
            Result.Success(Unit)
        } else {
            safeApiCall { api.logout(LogoutRequestDto(refresh)) }
        }
        sessionStore.clearSession()
        return result
    }
}
