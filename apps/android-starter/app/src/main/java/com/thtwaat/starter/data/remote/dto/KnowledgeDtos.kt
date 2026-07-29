package com.thtwaat.starter.data.remote.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

@Serializable
data class KnowledgeBaseCreateRequestDto(
    val name: String,
    val description: String? = null,
)

@Serializable
data class KnowledgeBaseDto(
    val id: String,
    val name: String,
    @SerialName("company_id") val companyId: String? = null,
    val description: String? = null,
    @SerialName("created_at") val createdAt: String? = null,
)

@Serializable
data class KnowledgeSearchRequestDto(
    val query: String,
    @SerialName("kb_id") val kbId: String? = null,
    @SerialName("top_k") val topK: Int = 5,
)

@Serializable
data class SearchResultItemDto(
    @SerialName("chunk_id") val chunkId: String? = null,
    @SerialName("document_id") val documentId: String? = null,
    val text: String? = null,
    val content: String? = null,
    val score: Double? = null,
    val metadata: JsonObject? = null,
)

@Serializable
data class KnowledgeDocumentDto(
    val id: String,
    @SerialName("knowledge_base_id") val knowledgeBaseId: String? = null,
    val name: String? = null,
    @SerialName("source_type") val sourceType: String? = null,
    val status: String? = null,
    @SerialName("file_size_bytes") val fileSizeBytes: Long? = null,
)
