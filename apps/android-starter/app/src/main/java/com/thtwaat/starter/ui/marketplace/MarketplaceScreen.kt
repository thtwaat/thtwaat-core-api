package com.thtwaat.starter.ui.marketplace

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
import com.thtwaat.starter.data.remote.dto.InstallationDto
import com.thtwaat.starter.data.remote.dto.TemplateItemDto
import com.thtwaat.starter.data.repository.MarketplaceRepository
import com.thtwaat.starter.ui.components.ErrorText
import com.thtwaat.starter.ui.components.ScreenPadding
import com.thtwaat.starter.ui.components.SectionCard
import com.thtwaat.starter.ui.components.SimpleField
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class MarketUi(
    val templates: List<TemplateItemDto> = emptyList(),
    val installed: List<InstallationDto> = emptyList(),
    val info: String? = null,
    val error: String? = null,
)

@HiltViewModel
class MarketplaceViewModel @Inject constructor(private val repo: MarketplaceRepository) : ViewModel() {
    private val _ui = MutableStateFlow(MarketUi())
    val ui = _ui.asStateFlow()
    init { refresh() }
    fun refresh(q: String? = null) = viewModelScope.launch {
        val t = repo.templates(q = q)
        val i = repo.installed()
        _ui.value = MarketUi(
            templates = (t as? Result.Success)?.data.orEmpty(),
            installed = (i as? Result.Success)?.data.orEmpty(),
            error = listOf(t, i).filterIsInstance<Result.Error>().firstOrNull()?.message,
        )
    }
    fun install(slug: String) = viewModelScope.launch {
        when (val r = repo.install(slug)) {
            is Result.Success -> { _ui.value = _ui.value.copy(info = "Installed ${r.data.id}"); refresh() }
            is Result.Error -> _ui.value = _ui.value.copy(error = r.message)
        }
    }
    fun connect(id: String) = act { repo.connect(id) }
    fun publish(id: String) = act { repo.publish(id) }
    fun update(id: String) = act { repo.update(id) }
    fun rollback(id: String) = act { repo.rollback(id) }
    fun uninstall(id: String) = act { repo.uninstall(id); Result.Success(Unit) }
    private fun <T> act(block: suspend () -> Result<T>) = viewModelScope.launch {
        when (val r = block()) {
            is Result.Success -> { _ui.value = _ui.value.copy(info = "OK"); refresh() }
            is Result.Error -> _ui.value = _ui.value.copy(error = r.message)
        }
    }
}

@Composable
fun MarketplaceScreen(vm: MarketplaceViewModel = hiltViewModel()) {
    val ui by vm.ui.collectAsState()
    var q by remember { mutableStateOf("") }
    ScreenPadding {
        Text("Marketplace", style = MaterialTheme.typography.headlineMedium)
        ErrorText(ui.error)
        if (ui.info != null) Text(ui.info!!)
        SimpleField(q, { q = it }, "Search templates")
        Button(onClick = { vm.refresh(q) }) { Text("Browse") }
        Text("Templates", style = MaterialTheme.typography.titleLarge)
        LazyColumn {
            items(ui.templates) { t ->
                SectionCard(t.name, "${t.category} · v${t.version}\n${t.description}", "Install") { vm.install(t.slug) }
            }
            item { Text("Installed", style = MaterialTheme.typography.titleLarge) }
            items(ui.installed) { i ->
                SectionCard(i.templateName ?: i.templateSlug ?: i.id, "status=${i.status} v=${i.installedVersion}")
                Button(onClick = { vm.connect(i.id) }) { Text("Connect") }
                Button(onClick = { vm.publish(i.id) }) { Text("Publish") }
                Button(onClick = { vm.update(i.id) }) { Text("Update") }
                Button(onClick = { vm.rollback(i.id) }) { Text("Rollback") }
                Button(onClick = { vm.uninstall(i.id) }) { Text("Uninstall") }
            }
        }
    }
}
