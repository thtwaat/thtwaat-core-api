package com.thtwaat.starter.ui.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.thtwaat.starter.core.util.Result
import com.thtwaat.starter.data.remote.dto.AgentDto
import com.thtwaat.starter.data.remote.dto.ConversationDto
import com.thtwaat.starter.data.remote.dto.UsageSnapshotDto
import com.thtwaat.starter.data.repository.AgentsRepository
import com.thtwaat.starter.data.repository.AnalyticsRepository
import com.thtwaat.starter.data.repository.ChatRepository
import com.thtwaat.starter.data.repository.UsageRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject
import javax.inject.Inject

data class HomeUiState(
    val loading: Boolean = true,
    val error: String? = null,
    val conversations: List<ConversationDto> = emptyList(),
    val agents: List<AgentDto> = emptyList(),
    val usage: UsageSnapshotDto? = null,
    val analytics: JsonObject? = null,
)

@HiltViewModel
class HomeViewModel @Inject constructor(
    private val chatRepository: ChatRepository,
    private val agentsRepository: AgentsRepository,
    private val usageRepository: UsageRepository,
    private val analyticsRepository: AnalyticsRepository,
) : ViewModel() {
    private val _ui = MutableStateFlow(HomeUiState())
    val ui = _ui.asStateFlow()

    init { refresh() }

    fun refresh() = viewModelScope.launch {
        _ui.value = _ui.value.copy(loading = true, error = null)
        val conv = chatRepository.history(5)
        val agents = agentsRepository.list()
        val usage = usageRepository.current()
        val analytics = analyticsRepository.overview()
        _ui.value = HomeUiState(
            loading = false,
            conversations = (conv as? Result.Success)?.data ?: chatRepository.cachedHistory().take(5),
            agents = (agents as? Result.Success)?.data ?: agentsRepository.cached().take(5),
            usage = (usage as? Result.Success)?.data,
            analytics = (analytics as? Result.Success)?.data,
            error = listOf(conv, agents, usage).filterIsInstance<Result.Error>().firstOrNull()?.message,
        )
    }
}
