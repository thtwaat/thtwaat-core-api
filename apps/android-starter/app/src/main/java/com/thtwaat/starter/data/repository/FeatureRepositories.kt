package com.thtwaat.starter.data.repository

import com.thtwaat.starter.core.network.safeApiCall
import com.thtwaat.starter.core.util.Result
import com.thtwaat.starter.data.local.dao.AgentDao
import com.thtwaat.starter.data.local.entity.AgentEntity
import com.thtwaat.starter.data.remote.api.AgentsApi
import com.thtwaat.starter.data.remote.api.AnalyticsApi
import com.thtwaat.starter.data.remote.api.BillingApi
import com.thtwaat.starter.data.remote.api.DomainsApi
import com.thtwaat.starter.data.remote.api.KnowledgeApi
import com.thtwaat.starter.data.remote.api.MarketplaceApi
import com.thtwaat.starter.data.remote.api.ProductGeneratorApi
import com.thtwaat.starter.data.remote.api.UsageApi
import com.thtwaat.starter.data.remote.dto.AgentCreateRequestDto
import com.thtwaat.starter.data.remote.dto.AgentDto
import com.thtwaat.starter.data.remote.dto.ConnectRequestDto
import com.thtwaat.starter.data.remote.dto.CreateApiKeyRequestDto
import com.thtwaat.starter.data.remote.dto.DomainCreateRequestDto
import com.thtwaat.starter.data.remote.dto.InstallRequestDto
import com.thtwaat.starter.data.remote.dto.KnowledgeBaseCreateRequestDto
import com.thtwaat.starter.data.remote.dto.KnowledgeSearchRequestDto
import com.thtwaat.starter.data.remote.dto.ProductAnalyzeRequestDto
import com.thtwaat.starter.data.remote.dto.ProductGenerateRequestDto
import com.thtwaat.starter.data.remote.dto.ProductPublishRequestDto
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class KnowledgeRepository @Inject constructor(private val api: KnowledgeApi) {
    suspend fun listBases() = safeApiCall { api.listBases() }
    suspend fun createBase(name: String, description: String?) =
        safeApiCall { api.createBase(KnowledgeBaseCreateRequestDto(name, description)) }
    suspend fun search(query: String, kbId: String? = null, topK: Int = 5) =
        safeApiCall { api.search(KnowledgeSearchRequestDto(query, kbId, topK)) }
    suspend fun upload(bytes: ByteArray, filename: String, kbId: String?) = safeApiCall {
        val body = bytes.toRequestBody("application/octet-stream".toMediaTypeOrNull())
        val part = MultipartBody.Part.createFormData("file", filename, body)
        api.upload(part, kbId)
    }
    suspend fun deleteDocument(id: String) = safeApiCall { api.deleteDocument(id) }
}

@Singleton
class AgentsRepository @Inject constructor(
    private val api: AgentsApi,
    private val agentDao: AgentDao,
) {
    private var cache: List<AgentDto> = emptyList()
    suspend fun list(): Result<List<AgentDto>> {
        val result = safeApiCall { api.list() }
        if (result is Result.Success) {
            cache = result.data
            agentDao.upsertAll(result.data.map { AgentEntity(it.id, it.name, it.status) })
        }
        return if (result is Result.Error && cache.isNotEmpty()) Result.Success(cache) else result
    }
    fun cached() = cache
    suspend fun get(id: String) = safeApiCall { api.get(id) }
    suspend fun create(name: String, prompt: String, description: String?) =
        safeApiCall { api.create(AgentCreateRequestDto(name, prompt, description)) }
    suspend fun publish(id: String) = safeApiCall { api.publish(id) }
    suspend fun unpublish(id: String) = safeApiCall { api.unpublish(id) }
    suspend fun embed(id: String) = safeApiCall { api.embed(id) }
    suspend fun widget(id: String) = safeApiCall { api.widget(id) }
    suspend fun listKeys(id: String) = safeApiCall { api.listApiKeys(id) }
    suspend fun createKey(id: String, name: String = "Default") =
        safeApiCall { api.createApiKey(id, CreateApiKeyRequestDto(name)) }
}

@Singleton
class MarketplaceRepository @Inject constructor(private val api: MarketplaceApi) {
    suspend fun templates(q: String? = null, category: String? = null) =
        safeApiCall { api.templates(q = q, category = category) }
    suspend fun template(idOrSlug: String) = safeApiCall { api.template(idOrSlug) }
    suspend fun install(idOrSlug: String) = safeApiCall { api.install(idOrSlug, InstallRequestDto()) }
    suspend fun installed() = safeApiCall { api.installed() }
    suspend fun updates() = safeApiCall { api.updates() }
    suspend fun connect(id: String, agentId: String? = null) =
        safeApiCall { api.connect(id, ConnectRequestDto(agentId = agentId)) }
    suspend fun publish(id: String) = safeApiCall { api.publish(id) }
    suspend fun update(id: String) = safeApiCall { api.update(id) }
    suspend fun rollback(id: String) = safeApiCall { api.rollback(id) }
    suspend fun uninstall(id: String) = safeApiCall { api.uninstall(id) }
    suspend fun dashboard() = safeApiCall { api.dashboard() }
}

@Singleton
class ProductGeneratorRepository @Inject constructor(private val api: ProductGeneratorApi) {
    suspend fun analyze(prompt: String) = safeApiCall { api.analyze(ProductAnalyzeRequestDto(prompt)) }
    suspend fun generate(prompt: String, templateSlug: String? = null, autoPublish: Boolean = false) =
        safeApiCall { api.generate(ProductGenerateRequestDto(prompt, templateSlug, autoPublish = autoPublish)) }
    suspend fun list() = safeApiCall { api.list() }
    suspend fun get(id: String) = safeApiCall { api.get(id) }
    suspend fun publish(id: String, hostname: String? = null) =
        safeApiCall { api.publish(id, ProductPublishRequestDto(hostname)) }
}

@Singleton
class DomainsRepository @Inject constructor(private val api: DomainsApi) {
    suspend fun list() = safeApiCall { api.list() }
    suspend fun create(hostname: String) = safeApiCall { api.create(DomainCreateRequestDto(hostname)) }
    suspend fun verify(id: String) = safeApiCall { api.verify(id) }
    suspend fun retry(id: String) = safeApiCall { api.retry(id) }
    suspend fun requestSsl(id: String) = safeApiCall { api.requestSsl(id) }
    suspend fun dashboard() = safeApiCall { api.dashboard() }
}

@Singleton
class UsageRepository @Inject constructor(private val api: UsageApi) {
    suspend fun current() = safeApiCall { api.current() }
    suspend fun dashboard() = safeApiCall { api.dashboard() }
}

@Singleton
class BillingRepository @Inject constructor(private val api: BillingApi) {
    suspend fun plans() = safeApiCall { api.plans() }
    suspend fun invoices() = safeApiCall { api.invoices() }
    suspend fun subscription() = safeApiCall { api.subscription() }
}

@Singleton
class AnalyticsRepository @Inject constructor(private val api: AnalyticsApi) {
    suspend fun overview() = safeApiCall { api.overview() }
}
