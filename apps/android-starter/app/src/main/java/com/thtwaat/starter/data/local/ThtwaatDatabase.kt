package com.thtwaat.starter.data.local

import androidx.room.Database
import androidx.room.RoomDatabase
import com.thtwaat.starter.data.local.dao.AgentDao
import com.thtwaat.starter.data.local.dao.ConversationDao
import com.thtwaat.starter.data.local.entity.AgentEntity
import com.thtwaat.starter.data.local.entity.ConversationEntity

@Database(
    entities = [ConversationEntity::class, AgentEntity::class],
    version = 1,
    exportSchema = false,
)
abstract class ThtwaatDatabase : RoomDatabase() {
    abstract fun conversationDao(): ConversationDao
    abstract fun agentDao(): AgentDao
}
