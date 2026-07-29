package com.thtwaat.starter.data.remote.api

import com.thtwaat.starter.data.remote.dto.ConnectRequestDto
import com.thtwaat.starter.data.remote.dto.InstallRequestDto
import com.thtwaat.starter.data.remote.dto.InstallationDto
import com.thtwaat.starter.data.remote.dto.TemplateItemDto
import com.thtwaat.starter.data.remote.dto.UpdateNotificationDto
import kotlinx.serialization.json.JsonObject
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

interface MarketplaceApi {
    @GET("/api/v1/marketplace/dashboard")
    suspend fun dashboard(): JsonObject

    @GET("/api/v1/marketplace/templates")
    suspend fun templates(
        @Query("q") q: String? = null,
        @Query("category") category: String? = null,
        @Query("featured") featured: Boolean? = null,
        @Query("newest") newest: Boolean? = null,
        @Query("limit") limit: Int = 50,
    ): List<TemplateItemDto>

    @GET("/api/v1/marketplace/templates/{idOrSlug}")
    suspend fun template(@Path("idOrSlug") idOrSlug: String): TemplateItemDto

    @POST("/api/v1/marketplace/templates/{idOrSlug}/install")
    suspend fun install(@Path("idOrSlug") idOrSlug: String, @Body body: InstallRequestDto): InstallationDto

    @GET("/api/v1/marketplace/installed")
    suspend fun installed(): List<InstallationDto>

    @GET("/api/v1/marketplace/updates")
    suspend fun updates(): List<UpdateNotificationDto>

    @POST("/api/v1/marketplace/installations/{id}/connect")
    suspend fun connect(@Path("id") id: String, @Body body: ConnectRequestDto): InstallationDto

    @POST("/api/v1/marketplace/installations/{id}/publish")
    suspend fun publish(@Path("id") id: String): InstallationDto

    @POST("/api/v1/marketplace/installations/{id}/update")
    suspend fun update(@Path("id") id: String, @Query("version") version: String? = null): InstallationDto

    @POST("/api/v1/marketplace/installations/{id}/rollback")
    suspend fun rollback(@Path("id") id: String): InstallationDto

    @DELETE("/api/v1/marketplace/installations/{id}")
    suspend fun uninstall(@Path("id") id: String)
}
