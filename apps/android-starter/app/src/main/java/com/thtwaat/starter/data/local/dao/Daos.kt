package com.thtwaat.starter.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.thtwaat.starter.data.local.entity.AgentEntity
import com.thtwaat.starter.data.local.entity.ConversationEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface ConversationDao {
    @Query("SELECT * FROM conversations ORDER BY cachedAt DESC LIMIT :limit")
    fun observeRecent(limit: Int = 20): Flow<List<ConversationEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(items: List<ConversationEntity>)

    @Query("DELETE FROM conversations")
    suspend fun clear()
}

@Dao
interface AgentDao {
    @Query("SELECT * FROM agents ORDER BY cachedAt DESC")
    fun observeAll(): Flow<List<AgentEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(items: List<AgentEntity>)

    @Query("DELETE FROM agents")
    suspend fun clear()
}
