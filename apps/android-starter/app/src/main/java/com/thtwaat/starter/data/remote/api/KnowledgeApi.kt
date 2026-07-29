package com.thtwaat.starter.data.remote.api

import com.thtwaat.starter.data.remote.dto.KnowledgeBaseCreateRequestDto
import com.thtwaat.starter.data.remote.dto.KnowledgeBaseDto
import com.thtwaat.starter.data.remote.dto.KnowledgeDocumentDto
import com.thtwaat.starter.data.remote.dto.KnowledgeSearchRequestDto
import com.thtwaat.starter.data.remote.dto.SearchResultItemDto
import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part
import retrofit2.http.Path
import retrofit2.http.Query

interface KnowledgeApi {
    @GET("/v2/knowledge/bases")
    suspend fun listBases(): List<KnowledgeBaseDto>

    @POST("/v2/knowledge/bases")
    suspend fun createBase(@Body body: KnowledgeBaseCreateRequestDto): KnowledgeBaseDto

    @POST("/v2/knowledge/search")
    suspend fun search(@Body body: KnowledgeSearchRequestDto): List<SearchResultItemDto>

    @Multipart
    @POST("/v2/knowledge/upload")
    suspend fun upload(
        @Part file: MultipartBody.Part,
        @Query("knowledge_base_id") kbId: String? = null,
    ): KnowledgeDocumentDto

    @DELETE("/v2/knowledge/documents/{id}")
    suspend fun deleteDocument(@Path("id") id: String)
}
