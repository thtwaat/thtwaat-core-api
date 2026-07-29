package com.thtwaat.starter.data.remote.api

import com.thtwaat.starter.data.remote.dto.ForgotPasswordRequestDto
import com.thtwaat.starter.data.remote.dto.LoginRequestDto
import com.thtwaat.starter.data.remote.dto.LogoutRequestDto
import com.thtwaat.starter.data.remote.dto.RefreshRequestDto
import com.thtwaat.starter.data.remote.dto.ResetPasswordRequestDto
import com.thtwaat.starter.data.remote.dto.SignupRequestDto
import com.thtwaat.starter.data.remote.dto.TokenResponseDto
import com.thtwaat.starter.data.remote.dto.UserProfileDto
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

interface AuthApi {
    @POST("/api/v1/auth/login")
    suspend fun login(@Body body: LoginRequestDto): TokenResponseDto

    @POST("/api/v1/auth/refresh")
    suspend fun refresh(@Body body: RefreshRequestDto): TokenResponseDto

    @POST("/api/v1/auth/logout")
    suspend fun logout(@Body body: LogoutRequestDto)

    @GET("/api/v1/auth/me")
    suspend fun me(): UserProfileDto

    @POST("/api/v1/auth/forgot-password")
    suspend fun forgotPassword(@Body body: ForgotPasswordRequestDto)

    @POST("/api/v1/auth/reset-password")
    suspend fun resetPassword(@Body body: ResetPasswordRequestDto)

    @POST("/api/v1/users/")
    suspend fun signup(@Body body: SignupRequestDto): UserProfileDto
}
