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
