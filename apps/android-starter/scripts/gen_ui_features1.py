from pathlib import Path
ROOT = Path(r"E:\THTWAAT\thtwaat-core-api\apps\android-starter")

def w(rel: str, content: str) -> None:
    path = ROOT / rel.replace("/", "\\")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.lstrip("\n"), encoding="utf-8", newline="\n")
    print("wrote", rel)

w("app/src/main/java/com/thtwaat/starter/ui/chat/ChatViewModel.kt", r'''
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
''')

w("app/src/main/java/com/thtwaat/starter/ui/chat/ChatScreen.kt", r'''
package com.thtwaat.starter.ui.chat

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.thtwaat.starter.core.util.MarkdownText
import com.thtwaat.starter.ui.components.ErrorText

@Composable
fun ChatScreen(vm: ChatViewModel = hiltViewModel()) {
    val ui by vm.ui.collectAsState()
    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        LazyColumn(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(ui.messages) { msg ->
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Text(msg.role.uppercase())
                        if (msg.role == "assistant") MarkdownText(msg.content) else Text(msg.content)
                    }
                }
            }
            if (ui.typing) item { Text("Assistant is typing...") }
        }
        ErrorText(ui.error)
        LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(vertical = 8.dp)) {
            items(ui.suggested) { s -> AssistChip(onClick = { vm.useSuggestion(s) }, label = { Text(s) }) }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
            OutlinedTextField(value = ui.input, onValueChange = vm::onInput, modifier = Modifier.weight(1f), label = { Text("Message") })
            Button(onClick = { vm.send(true) }, enabled = !ui.streaming) { Text("Send") }
        }
        Row {
            TextButton(onClick = vm::stop, enabled = ui.streaming) { Text("Stop") }
            TextButton(onClick = vm::retry, enabled = !ui.streaming) { Text("Retry") }
        }
    }
}
''')

w("app/src/main/java/com/thtwaat/starter/ui/knowledge/KnowledgeScreen.kt", r'''
package com.thtwaat.starter.ui.knowledge

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.thtwaat.starter.core.util.Result
import com.thtwaat.starter.data.remote.dto.KnowledgeBaseDto
import com.thtwaat.starter.data.remote.dto.SearchResultItemDto
import com.thtwaat.starter.data.repository.KnowledgeRepository
import com.thtwaat.starter.ui.components.ErrorText
import com.thtwaat.starter.ui.components.ScreenPadding
import com.thtwaat.starter.ui.components.SectionCard
import com.thtwaat.starter.ui.components.SimpleField
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class KnowledgeUi(
    val bases: List<KnowledgeBaseDto> = emptyList(),
    val results: List<SearchResultItemDto> = emptyList(),
    val error: String? = null,
    val message: String? = null,
)

@HiltViewModel
class KnowledgeViewModel @Inject constructor(private val repo: KnowledgeRepository) : ViewModel() {
    private val _ui = MutableStateFlow(KnowledgeUi())
    val ui = _ui.asStateFlow()
    init { refresh() }
    fun refresh() = viewModelScope.launch {
        when (val r = repo.listBases()) {
            is Result.Success -> _ui.value = _ui.value.copy(bases = r.data, error = null)
            is Result.Error -> _ui.value = _ui.value.copy(error = r.message)
        }
    }
    fun create(name: String) = viewModelScope.launch {
        when (val r = repo.createBase(name, null)) {
            is Result.Success -> refresh()
            is Result.Error -> _ui.value = _ui.value.copy(error = r.message)
        }
    }
    fun search(query: String) = viewModelScope.launch {
        when (val r = repo.search(query)) {
            is Result.Success -> _ui.value = _ui.value.copy(results = r.data)
            is Result.Error -> _ui.value = _ui.value.copy(error = r.message)
        }
    }
    fun delete(id: String) = viewModelScope.launch {
        when (val r = repo.deleteDocument(id)) {
            is Result.Success -> _ui.value = _ui.value.copy(message = "Deleted $id")
            is Result.Error -> _ui.value = _ui.value.copy(error = r.message)
        }
    }
}

@Composable
fun KnowledgeScreen(vm: KnowledgeViewModel = hiltViewModel()) {
    val ui by vm.ui.collectAsState()
    var name by remember { mutableStateOf("") }
    var query by remember { mutableStateOf("") }
    ScreenPadding {
        Text("Knowledge", style = MaterialTheme.typography.headlineMedium)
        ErrorText(ui.error)
        if (ui.message != null) Text(ui.message!!)
        SimpleField(name, { name = it }, "New knowledge base")
        Button(onClick = { vm.create(name) }) { Text("Create") }
        SimpleField(query, { query = it }, "Search")
        Button(onClick = { vm.search(query) }) { Text("Search") }
        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(ui.bases) { b -> SectionCard(b.name, b.description ?: b.id) }
            items(ui.results) { r ->
                SectionCard(
                    title = "score ${r.score ?: 0.0}",
                    body = r.text ?: r.content.orEmpty(),
                    actionLabel = if (r.documentId != null) "Delete" else null,
                    onAction = r.documentId?.let { id -> { vm.delete(id) } },
                )
            }
        }
    }
}
''')

w("app/src/main/java/com/thtwaat/starter/ui/agents/AgentsScreen.kt", r'''
package com.thtwaat.starter.ui.agents

import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.thtwaat.starter.core.util.Result
import com.thtwaat.starter.data.remote.dto.AgentDto
import com.thtwaat.starter.data.repository.AgentsRepository
import com.thtwaat.starter.ui.components.ErrorText
import com.thtwaat.starter.ui.components.ScreenPadding
import com.thtwaat.starter.ui.components.SectionCard
import com.thtwaat.starter.ui.components.SimpleField
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class AgentsUi(val agents: List<AgentDto> = emptyList(), val info: String? = null, val error: String? = null)

@HiltViewModel
class AgentsViewModel @Inject constructor(private val repo: AgentsRepository) : ViewModel() {
    private val _ui = MutableStateFlow(AgentsUi())
    val ui = _ui.asStateFlow()
    init { refresh() }
    fun refresh() = viewModelScope.launch {
        when (val r = repo.list()) {
            is Result.Success -> _ui.value = AgentsUi(agents = r.data)
            is Result.Error -> _ui.value = AgentsUi(agents = repo.cached(), error = r.message)
        }
    }
    fun create(name: String, prompt: String) = viewModelScope.launch {
        when (val r = repo.create(name, prompt, null)) {
            is Result.Success -> refresh()
            is Result.Error -> _ui.value = _ui.value.copy(error = r.message)
        }
    }
    fun publish(id: String) = viewModelScope.launch {
        when (val r = repo.publish(id)) {
            is Result.Success -> _ui.value = _ui.value.copy(info = "Published ${r.data.agentId} key=${r.data.apiKey ?: "-"}")
            is Result.Error -> _ui.value = _ui.value.copy(error = r.message)
        }
    }
    fun createKey(id: String) = viewModelScope.launch {
        when (val r = repo.createKey(id)) {
            is Result.Success -> _ui.value = _ui.value.copy(info = "API key: ${r.data.apiKey ?: r.data.plainKey ?: r.data.keyPrefix}")
            is Result.Error -> _ui.value = _ui.value.copy(error = r.message)
        }
    }
    fun widget(id: String) = viewModelScope.launch {
        when (val r = repo.widget(id)) {
            is Result.Success -> _ui.value = _ui.value.copy(info = r.data.toString().take(200))
            is Result.Error -> _ui.value = _ui.value.copy(error = r.message)
        }
    }
}

@Composable
fun AgentsScreen(vm: AgentsViewModel = hiltViewModel()) {
    val ui by vm.ui.collectAsState()
    var name by remember { mutableStateOf("") }
    var prompt by remember { mutableStateOf("You are a helpful assistant.") }
    ScreenPadding {
        Text("Agents", style = MaterialTheme.typography.headlineMedium)
        ErrorText(ui.error)
        if (ui.info != null) Text(ui.info!!)
        SimpleField(name, { name = it }, "Name")
        SimpleField(prompt, { prompt = it }, "System prompt")
        Button(onClick = { vm.create(name, prompt) }) { Text("Create") }
        LazyColumn {
            items(ui.agents) { a ->
                SectionCard(
                    title = a.name,
                    body = "${a.status ?: "-"} · ${a.id}",
                    actionLabel = "Publish",
                    onAction = { vm.publish(a.id) },
                )
                Button(onClick = { vm.createKey(a.id) }) { Text("API Key") }
                Button(onClick = { vm.widget(a.id) }) { Text("Widget") }
            }
        }
    }
}
''')

print("chat/knowledge/agents done")
