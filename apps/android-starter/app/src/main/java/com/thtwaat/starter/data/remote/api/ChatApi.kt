package com.thtwaat.starter.data.remote.api

import com.thtwaat.starter.data.remote.dto.ChatRequestDto
import com.thtwaat.starter.data.remote.dto.ChatResponseDto
import com.thtwaat.starter.data.remote.dto.ConversationDto
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

interface ChatApi {
    @POST("/public/v1/chat")
    suspend fun chat(@Body body: ChatRequestDto): ChatResponseDto

    @GET("/v2/conversations")
    suspend fun conversations(@Query("limit") limit: Int? = null): List<ConversationDto>

    @GET("/v2/conversations/{id}")
    suspend fun conversation(@Path("id") id: String): ConversationDto
}
