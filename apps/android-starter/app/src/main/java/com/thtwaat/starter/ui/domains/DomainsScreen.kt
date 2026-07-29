package com.thtwaat.starter.ui.domains

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
import com.thtwaat.starter.data.remote.dto.DomainRecordDto
import com.thtwaat.starter.data.repository.DomainsRepository
import com.thtwaat.starter.ui.components.ErrorText
import com.thtwaat.starter.ui.components.ScreenPadding
import com.thtwaat.starter.ui.components.SectionCard
import com.thtwaat.starter.ui.components.SimpleField
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class DomainsUi(val domains: List<DomainRecordDto> = emptyList(), val error: String? = null)

@HiltViewModel
class DomainsViewModel @Inject constructor(private val repo: DomainsRepository) : ViewModel() {
    private val _ui = MutableStateFlow(DomainsUi())
    val ui = _ui.asStateFlow()
    init { refresh() }
    fun refresh() = viewModelScope.launch {
        when (val r = repo.list()) {
            is Result.Success -> _ui.value = DomainsUi(domains = r.data)
            is Result.Error -> _ui.value = DomainsUi(error = r.message)
        }
    }
    fun add(hostname: String) = viewModelScope.launch {
        when (val r = repo.create(hostname)) {
            is Result.Success -> refresh()
            is Result.Error -> _ui.value = _ui.value.copy(error = r.message)
        }
    }
    fun verify(id: String) = viewModelScope.launch { repo.verify(id); refresh() }
    fun retry(id: String) = viewModelScope.launch { repo.retry(id); refresh() }
    fun ssl(id: String) = viewModelScope.launch { repo.requestSsl(id); refresh() }
}

@Composable
fun DomainsScreen(vm: DomainsViewModel = hiltViewModel()) {
    val ui by vm.ui.collectAsState()
    var host by remember { mutableStateOf("") }
    ScreenPadding {
        Text("Domains", style = MaterialTheme.typography.headlineMedium)
        ErrorText(ui.error)
        SimpleField(host, { host = it }, "Hostname")
        Button(onClick = { vm.add(host) }) { Text("Add domain") }
        LazyColumn {
            items(ui.domains) { d ->
                SectionCard(d.hostname, "status=${d.status} ssl=${d.sslStatus}\ntoken=${d.verificationToken ?: "-"}")
                Button(onClick = { vm.verify(d.id) }) { Text("Verify") }
                Button(onClick = { vm.retry(d.id) }) { Text("Retry") }
                Button(onClick = { vm.ssl(d.id) }) { Text("SSL status/request") }
            }
        }
    }
}
