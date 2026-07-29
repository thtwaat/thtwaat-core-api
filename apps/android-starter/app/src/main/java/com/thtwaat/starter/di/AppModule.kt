package com.thtwaat.starter.di

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.preferencesDataStore
import androidx.room.Room
import com.thtwaat.starter.data.local.ThtwaatDatabase
import com.thtwaat.starter.data.local.dao.AgentDao
import com.thtwaat.starter.data.local.dao.ConversationDao
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

private val Context.dataStore by preferencesDataStore(name = "thtwaat_session")

@Module
@InstallIn(SingletonComponent::class)
object AppModule {
    @Provides
    @Singleton
    fun provideDataStore(@ApplicationContext context: Context): DataStore<Preferences> =
        context.dataStore

    @Provides
    @Singleton
    fun provideDatabase(@ApplicationContext context: Context): ThtwaatDatabase =
        Room.databaseBuilder(context, ThtwaatDatabase::class.java, "thtwaat_cache.db").build()

    @Provides
    fun provideConversationDao(db: ThtwaatDatabase): ConversationDao = db.conversationDao()

    @Provides
    fun provideAgentDao(db: ThtwaatDatabase): AgentDao = db.agentDao()
}
