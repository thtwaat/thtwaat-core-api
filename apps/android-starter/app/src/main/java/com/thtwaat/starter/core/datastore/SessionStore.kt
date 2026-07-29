package com.thtwaat.starter.core.datastore

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class SessionStore @Inject constructor(
    private val dataStore: DataStore<Preferences>,
) {
    private val access = stringPreferencesKey("access_token")
    private val refresh = stringPreferencesKey("refresh_token")
    private val apiKey = stringPreferencesKey("api_key")
    private val theme = stringPreferencesKey("theme_mode")

    val accessToken: Flow<String?> = dataStore.data.map { it[access] }
    val refreshToken: Flow<String?> = dataStore.data.map { it[refresh] }
    val agentApiKey: Flow<String?> = dataStore.data.map { it[apiKey] }
    val themeMode: Flow<String> = dataStore.data.map { it[theme] ?: "system" }

    suspend fun getAccessToken(): String? = accessToken.first()
    suspend fun getRefreshToken(): String? = refreshToken.first()
    suspend fun getApiKey(): String? = agentApiKey.first()

    suspend fun saveTokens(accessToken: String, refreshToken: String) {
        dataStore.edit {
            it[access] = accessToken
            it[refresh] = refreshToken
        }
    }

    suspend fun saveApiKey(key: String) {
        dataStore.edit { it[apiKey] = key }
    }

    suspend fun setTheme(mode: String) {
        dataStore.edit { it[theme] = mode }
    }

    suspend fun clearSession() {
        dataStore.edit {
            it.remove(access)
            it.remove(refresh)
        }
    }

    suspend fun clearAll() {
        dataStore.edit { it.clear() }
    }
}
