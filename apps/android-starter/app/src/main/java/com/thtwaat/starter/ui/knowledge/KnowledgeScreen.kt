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
