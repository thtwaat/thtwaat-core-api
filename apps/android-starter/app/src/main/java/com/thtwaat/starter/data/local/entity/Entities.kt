package com.thtwaat.starter.data.local.entity

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "conversations")
data class ConversationEntity(
    @PrimaryKey val id: String,
    val title: String,
    val updatedAt: String?,
    val cachedAt: Long = System.currentTimeMillis(),
)

@Entity(tableName = "agents")
data class AgentEntity(
    @PrimaryKey val id: String,
    val name: String,
    val status: String?,
    val cachedAt: Long = System.currentTimeMillis(),
)
