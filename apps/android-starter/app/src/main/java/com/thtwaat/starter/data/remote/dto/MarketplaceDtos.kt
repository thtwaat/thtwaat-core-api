package com.thtwaat.starter.data.remote.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

@Serializable
data class TemplateItemDto(
    val id: String,
    val slug: String,
    val name: String,
    val category: String = "",
    val description: String = "",
    val version: String = "",
    val tags: List<String> = emptyList(),
    val author: String? = null,
    val status: String? = null,
    @SerialName("is_public") val isPublic: Boolean = true,
    @SerialName("is_featured") val isFeatured: Boolean = false,
    val installed: Boolean = false,
    @SerialName("update_available") val updateAvailable: Boolean = false,
    @SerialName("install_count") val installCount: Int = 0,
)

@Serializable
data class InstallationDto(
    val id: String,
    @SerialName("template_id") val templateId: String,
    @SerialName("template_slug") val templateSlug: String? = null,
    @SerialName("template_name") val templateName: String? = null,
    @SerialName("installed_version") val installedVersion: String = "",
    @SerialName("previous_version") val previousVersion: String? = null,
    val status: String = "",
    @SerialName("agent_id") val agentId: String? = null,
    @SerialName("api_key") val apiKey: String? = null,
    @SerialName("domain_id") val domainId: String? = null,
    @SerialName("update_available") val updateAvailable: Boolean = false,
    @SerialName("latest_available_version") val latestAvailableVersion: String? = null,
    val config: JsonObject? = null,
)

@Serializable
data class InstallRequestDto(
    @SerialName("create_api_key") val createApiKey: Boolean = true,
    @SerialName("agent_id") val agentId: String? = null,
    @SerialName("config_overrides") val configOverrides: JsonObject? = null,
)

@Serializable
data class ConnectRequestDto(
    @SerialName("agent_id") val agentId: String? = null,
    @SerialName("domain_id") val domainId: String? = null,
    @SerialName("create_api_key") val createApiKey: Boolean = true,
)

@Serializable
data class UpdateNotificationDto(
    @SerialName("installation_id") val installationId: String,
    @SerialName("template_id") val templateId: String,
    @SerialName("template_slug") val templateSlug: String = "",
    @SerialName("template_name") val templateName: String = "",
    @SerialName("installed_version") val installedVersion: String = "",
    @SerialName("latest_version") val latestVersion: String = "",
    val changelog: String? = null,
)
