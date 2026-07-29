package com.thtwaat.starter.data.remote.api

import com.thtwaat.starter.data.remote.dto.DomainCreateRequestDto
import com.thtwaat.starter.data.remote.dto.DomainRecordDto
import com.thtwaat.starter.data.remote.dto.InvoiceDto
import com.thtwaat.starter.data.remote.dto.PlanDto
import com.thtwaat.starter.data.remote.dto.ProductAnalysisDto
import com.thtwaat.starter.data.remote.dto.ProductAnalyzeRequestDto
import com.thtwaat.starter.data.remote.dto.ProductGenerateRequestDto
import com.thtwaat.starter.data.remote.dto.ProductGenerationDto
import com.thtwaat.starter.data.remote.dto.ProductPublishRequestDto
import com.thtwaat.starter.data.remote.dto.SubscriptionDto
import com.thtwaat.starter.data.remote.dto.UsageSnapshotDto
import kotlinx.serialization.json.JsonObject
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

interface ProductGeneratorApi {
    @POST("/api/v1/product-generator/analyze")
    suspend fun analyze(@Body body: ProductAnalyzeRequestDto): ProductAnalysisDto

    @POST("/api/v1/product-generator/generate")
    suspend fun generate(@Body body: ProductGenerateRequestDto): ProductGenerationDto

    @GET("/api/v1/product-generator/generations")
    suspend fun list(): List<ProductGenerationDto>

    @GET("/api/v1/product-generator/generations/{id}")
    suspend fun get(@Path("id") id: String): ProductGenerationDto

    @POST("/api/v1/product-generator/generations/{id}/publish")
    suspend fun publish(@Path("id") id: String, @Body body: ProductPublishRequestDto): ProductGenerationDto
}

interface DomainsApi {
    @GET("/api/v1/domains/dashboard")
    suspend fun dashboard(): JsonObject

    @GET("/api/v1/domains/")
    suspend fun list(): List<DomainRecordDto>

    @POST("/api/v1/domains/")
    suspend fun create(@Body body: DomainCreateRequestDto): DomainRecordDto

    @GET("/api/v1/domains/{id}")
    suspend fun get(@Path("id") id: String): DomainRecordDto

    @POST("/api/v1/domains/{id}/verify")
    suspend fun verify(@Path("id") id: String): DomainRecordDto

    @POST("/api/v1/domains/{id}/retry")
    suspend fun retry(@Path("id") id: String): DomainRecordDto

    @POST("/api/v1/domains/{id}/ssl/request")
    suspend fun requestSsl(@Path("id") id: String): DomainRecordDto
}

interface UsageApi {
    @GET("/api/v1/usage/current")
    suspend fun current(): UsageSnapshotDto

    @GET("/api/v1/usage/dashboard")
    suspend fun dashboard(): JsonObject

    @GET("/api/v1/usage/history")
    suspend fun history(): List<JsonObject>
}

interface BillingApi {
    @GET("/api/v1/payments/plans/")
    suspend fun plans(): List<PlanDto>

    @GET("/api/v1/payments/invoices/")
    suspend fun invoices(): List<InvoiceDto>

    @GET("/api/v1/payments/subscriptions/me")
    suspend fun subscription(): SubscriptionDto
}

interface AnalyticsApi {
    @GET("/api/v1/analytics/overview")
    suspend fun overview(): JsonObject
}
