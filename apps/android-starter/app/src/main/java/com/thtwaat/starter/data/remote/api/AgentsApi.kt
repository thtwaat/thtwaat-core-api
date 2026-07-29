package com.thtwaat.starter.data.remote.api

import com.thtwaat.starter.data.remote.dto.AgentApiKeyDto
import com.thtwaat.starter.data.remote.dto.AgentCreateRequestDto
import com.thtwaat.starter.data.remote.dto.AgentDto
import com.thtwaat.starter.data.remote.dto.CreateApiKeyRequestDto
import com.thtwaat.starter.data.remote.dto.PublishResultDto
import kotlinx.serialization.json.JsonObject
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

interface AgentsApi {
    @GET("/v2/agents")
    suspend fun list(@Query("is_template") isTemplate: Boolean? = null): List<AgentDto>

    @GET("/v2/agents/{id}")
    suspend fun get(@Path("id") id: String): AgentDto

    @POST("/v2/agents")
    suspend fun create(@Body body: AgentCreateRequestDto): AgentDto

    @POST("/api/v1/agents/{id}/publish")
    suspend fun publish(@Path("id") id: String): PublishResultDto

    @POST("/api/v1/agents/{id}/unpublish")
    suspend fun unpublish(@Path("id") id: String)

    @GET("/api/v1/agents/{id}/embed")
    suspend fun embed(@Path("id") id: String): JsonObject

    @GET("/api/v1/agents/{id}/widget")
    suspend fun widget(@Path("id") id: String): JsonObject

    @PATCH("/api/v1/agents/{id}/widget")
    suspend fun updateWidget(@Path("id") id: String, @Body body: JsonObject): JsonObject

    @GET("/api/v1/agents/{id}/api-keys")
    suspend fun listApiKeys(@Path("id") id: String): List<AgentApiKeyDto>

    @POST("/api/v1/agents/{id}/api-keys")
    suspend fun createApiKey(@Path("id") id: String, @Body body: CreateApiKeyRequestDto): AgentApiKeyDto
}
