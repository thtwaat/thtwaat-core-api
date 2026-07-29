package com.thtwaat.starter.di

import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import com.thtwaat.starter.BuildConfig
import com.thtwaat.starter.core.network.AuthInterceptor
import com.thtwaat.starter.core.network.TokenAuthenticator
import com.thtwaat.starter.data.remote.api.AgentsApi
import com.thtwaat.starter.data.remote.api.AnalyticsApi
import com.thtwaat.starter.data.remote.api.AuthApi
import com.thtwaat.starter.data.remote.api.BillingApi
import com.thtwaat.starter.data.remote.api.ChatApi
import com.thtwaat.starter.data.remote.api.DomainsApi
import com.thtwaat.starter.data.remote.api.KnowledgeApi
import com.thtwaat.starter.data.remote.api.MarketplaceApi
import com.thtwaat.starter.data.remote.api.ProductGeneratorApi
import com.thtwaat.starter.data.remote.api.UsageApi
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import java.util.concurrent.TimeUnit
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {
    @Provides
    @Singleton
    fun provideJson(): Json = Json {
        ignoreUnknownKeys = true
        isLenient = true
        encodeDefaults = true
    }

    @Provides
    @Singleton
    fun provideOkHttp(
        authInterceptor: AuthInterceptor,
        authenticator: TokenAuthenticator,
    ): OkHttpClient {
        val logging = HttpLoggingInterceptor().apply {
            level = if (BuildConfig.DEBUG) HttpLoggingInterceptor.Level.BASIC else HttpLoggingInterceptor.Level.NONE
        }
        return OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(90, TimeUnit.SECONDS)
            .writeTimeout(90, TimeUnit.SECONDS)
            .addInterceptor(authInterceptor)
            .authenticator(authenticator)
            .addInterceptor(logging)
            .build()
    }

    @Provides
    @Singleton
    fun provideRetrofit(client: OkHttpClient, json: Json): Retrofit {
        val contentType = "application/json".toMediaType()
        return Retrofit.Builder()
            .baseUrl(BuildConfig.API_BASE_URL.trimEnd('/') + "/")
            .client(client)
            .addConverterFactory(json.asConverterFactory(contentType))
            .build()
    }

    @Provides @Singleton fun authApi(r: Retrofit): AuthApi = r.create(AuthApi::class.java)
    @Provides @Singleton fun chatApi(r: Retrofit): ChatApi = r.create(ChatApi::class.java)
    @Provides @Singleton fun knowledgeApi(r: Retrofit): KnowledgeApi = r.create(KnowledgeApi::class.java)
    @Provides @Singleton fun agentsApi(r: Retrofit): AgentsApi = r.create(AgentsApi::class.java)
    @Provides @Singleton fun marketplaceApi(r: Retrofit): MarketplaceApi = r.create(MarketplaceApi::class.java)
    @Provides @Singleton fun productApi(r: Retrofit): ProductGeneratorApi = r.create(ProductGeneratorApi::class.java)
    @Provides @Singleton fun domainsApi(r: Retrofit): DomainsApi = r.create(DomainsApi::class.java)
    @Provides @Singleton fun usageApi(r: Retrofit): UsageApi = r.create(UsageApi::class.java)
    @Provides @Singleton fun billingApi(r: Retrofit): BillingApi = r.create(BillingApi::class.java)
    @Provides @Singleton fun analyticsApi(r: Retrofit): AnalyticsApi = r.create(AnalyticsApi::class.java)
}
