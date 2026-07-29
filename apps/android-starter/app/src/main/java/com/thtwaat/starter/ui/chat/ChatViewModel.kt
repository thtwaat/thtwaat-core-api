package com.thtwaat.starter.ui.chat

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.thtwaat.starter.core.util.Result
import com.thtwaat.starter.data.repository.ChatRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class ChatMessage(val role: String, val content: String)

data class ChatUiState(
    val messages: List<ChatMessage> = emptyList(),
    val input: String = "",
    val streaming: Boolean = false,
    val typing: Boolean = false,
    val error: String? = null,
    val suggested: List<String> = listOf("Summarize my product", "Draft a welcome reply", "Explain pricing"),
    val sessionId: String? = null,
)

@HiltViewModel
class ChatViewModel @Inject constructor(
    private val repo: ChatRepository,
) : ViewModel() {
    private val _ui = MutableStateFlow(ChatUiState())
    val ui = _ui.asStateFlow()
    private var streamJob: Job? = null
    private var lastUserMessage: String? = null

    fun onInput(value: String) = _ui.update { it.copy(input = value) }

    fun send(stream: Boolean = true) {
        val text = _ui.value.input.trim()
        if (text.isEmpty() || _ui.value.streaming) return
        lastUserMessage = text
        _ui.update {
            it.copy(
                messages = it.messages + ChatMessage("user", text),
                input = "",
                streaming = true,
                typing = true,
                error = null,
            )
        }
        if (stream) startStream(text) else sendOnce(text)
    }

    private fun sendOnce(text: String) = viewModelScope.launch {
        when (val r = repo.chat(text, _ui.value.sessionId)) {
            is Result.Success -> _ui.update {
                it.copy(
                    streaming = false,
                    typing = false,
                    sessionId = r.data.conversationId ?: it.sessionId,
                    suggested = r.data.suggestedPrompts.ifEmpty { it.suggested },
                    messages = it.messages + ChatMessage("assistant", r.data.reply ?: r.data.response.orEmpty()),
                )
            }
            is Result.Error -> _ui.update { it.copy(streaming = false, typing = false, error = r.message) }
        }
    }

    private fun startStream(text: String) {
        streamJob?.cancel()
        streamJob = viewModelScope.launch {
            val buffer = StringBuilder()
            try {
                repo.stream(text, _ui.value.sessionId).collect { token ->
                    when (token.event) {
                        "token", "message" -> {
                            val chunk = token.text.orEmpty()
                            if (chunk.isNotEmpty()) {
                                buffer.append(chunk)
                                val content = buffer.toString()
                                _ui.update { state ->
                                    val msgs = state.messages.toMutableList()
                                    if (msgs.lastOrNull()?.role == "assistant") {
                                        msgs[msgs.lastIndex] = ChatMessage("assistant", content)
                                    } else {
                                        msgs += ChatMessage("assistant", content)
                                    }
                                    state.copy(messages = msgs, typing = true)
                                }
                            }
                        }
                        "done" -> _ui.update { it.copy(streaming = false, typing = false) }
                        "error" -> _ui.update { it.copy(streaming = false, typing = false, error = token.text ?: "Stream error") }
                    }
                }
                _ui.update { it.copy(streaming = false, typing = false) }
            } catch (e: Exception) {
                _ui.update { it.copy(streaming = false, typing = false, error = e.message) }
            }
        }
    }

    fun stop() {
        streamJob?.cancel()
        _ui.update { it.copy(streaming = false, typing = false) }
    }

    fun retry() {
        val msg = lastUserMessage ?: return
        _ui.update { it.copy(input = msg) }
        send(stream = true)
    }

    fun useSuggestion(text: String) {
        _ui.update { it.copy(input = text) }
        send(stream = true)
    }
}
