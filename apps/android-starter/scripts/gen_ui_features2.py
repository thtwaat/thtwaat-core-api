from pathlib import Path
ROOT = Path(r"E:\THTWAAT\thtwaat-core-api\apps\android-starter")

def w(rel: str, content: str) -> None:
    path = ROOT / rel.replace("/", "\\")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.lstrip("\n"), encoding="utf-8", newline="\n")
    print("wrote", rel)

w("app/src/main/java/com/thtwaat/starter/ui/marketplace/MarketplaceScreen.kt", r'''
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
''')

w("app/src/main/java/com/thtwaat/starter/ui/productgenerator/ProductGeneratorScreen.kt", r'''
package com.thtwaat.starter.ui.productgenerator

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
import com.thtwaat.starter.data.remote.dto.ProductAnalysisDto
import com.thtwaat.starter.data.remote.dto.ProductGenerationDto
import com.thtwaat.starter.data.repository.ProductGeneratorRepository
import com.thtwaat.starter.ui.components.ErrorText
import com.thtwaat.starter.ui.components.ScreenPadding
import com.thtwaat.starter.ui.components.SectionCard
import com.thtwaat.starter.ui.components.SimpleField
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class ProductUi(
    val analysis: ProductAnalysisDto? = null,
    val generation: ProductGenerationDto? = null,
    val error: String? = null,
)

@HiltViewModel
class ProductGeneratorViewModel @Inject constructor(private val repo: ProductGeneratorRepository) : ViewModel() {
    private val _ui = MutableStateFlow(ProductUi())
    val ui = _ui.asStateFlow()
    fun analyze(prompt: String) = viewModelScope.launch {
        when (val r = repo.analyze(prompt)) {
            is Result.Success -> _ui.value = ProductUi(analysis = r.data)
            is Result.Error -> _ui.value = ProductUi(error = r.message)
        }
    }
    fun generate(prompt: String) = viewModelScope.launch {
        val slug = _ui.value.analysis?.recommendedTemplateSlug
        when (val r = repo.generate(prompt, slug)) {
            is Result.Success -> _ui.value = _ui.value.copy(generation = r.data, error = null)
            is Result.Error -> _ui.value = _ui.value.copy(error = r.message)
        }
    }
    fun publish() = viewModelScope.launch {
        val id = _ui.value.generation?.id ?: return@launch
        when (val r = repo.publish(id)) {
            is Result.Success -> _ui.value = _ui.value.copy(generation = r.data)
            is Result.Error -> _ui.value = _ui.value.copy(error = r.message)
        }
    }
}

@Composable
fun ProductGeneratorScreen(vm: ProductGeneratorViewModel = hiltViewModel()) {
    val ui by vm.ui.collectAsState()
    var prompt by remember { mutableStateOf("Restaurant website with AI ordering") }
    ScreenPadding {
        Text("Product Generator", style = MaterialTheme.typography.headlineMedium)
        ErrorText(ui.error)
        SimpleField(prompt, { prompt = it }, "Describe your product")
        Button(onClick = { vm.analyze(prompt) }) { Text("1. Analyze") }
        ui.analysis?.let {
            SectionCard("Analysis", "${it.suggestedName}\n${it.industry}/${it.category}\nconfidence=${it.confidence}")
        }
        Button(onClick = { vm.generate(prompt) }) { Text("2. Generate") }
        ui.generation?.let {
            SectionCard("Preview", "status=${it.status}\n${it.previewUrl ?: "No preview yet"}")
            Button(onClick = { vm.publish() }) { Text("3. Publish") }
        }
    }
}
''')

w("app/src/main/java/com/thtwaat/starter/ui/domains/DomainsScreen.kt", r'''
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
''')

w("app/src/main/java/com/thtwaat/starter/ui/billing/BillingScreen.kt", r'''
package com.thtwaat.starter.ui.billing

import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.thtwaat.starter.core.util.Result
import com.thtwaat.starter.data.remote.dto.InvoiceDto
import com.thtwaat.starter.data.remote.dto.PlanDto
import com.thtwaat.starter.data.remote.dto.SubscriptionDto
import com.thtwaat.starter.data.remote.dto.UsageSnapshotDto
import com.thtwaat.starter.data.repository.BillingRepository
import com.thtwaat.starter.data.repository.UsageRepository
import com.thtwaat.starter.ui.components.ErrorText
import com.thtwaat.starter.ui.components.ScreenPadding
import com.thtwaat.starter.ui.components.SectionCard
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class BillingUi(
    val plans: List<PlanDto> = emptyList(),
    val invoices: List<InvoiceDto> = emptyList(),
    val subscription: SubscriptionDto? = null,
    val usage: UsageSnapshotDto? = null,
    val error: String? = null,
)

@HiltViewModel
class BillingViewModel @Inject constructor(
    private val billing: BillingRepository,
    private val usage: UsageRepository,
) : ViewModel() {
    private val _ui = MutableStateFlow(BillingUi())
    val ui = _ui.asStateFlow()
    init {
        viewModelScope.launch {
            val p = billing.plans()
            val i = billing.invoices()
            val s = billing.subscription()
            val u = usage.current()
            _ui.value = BillingUi(
                plans = (p as? Result.Success)?.data.orEmpty(),
                invoices = (i as? Result.Success)?.data.orEmpty(),
                subscription = (s as? Result.Success)?.data,
                usage = (u as? Result.Success)?.data,
                error = listOf(p, i, s, u).filterIsInstance<Result.Error>().firstOrNull()?.message,
            )
        }
    }
}

@Composable
fun BillingScreen(vm: BillingViewModel = hiltViewModel()) {
    val ui by vm.ui.collectAsState()
    ScreenPadding {
        Text("Billing", style = MaterialTheme.typography.headlineMedium)
        ErrorText(ui.error)
        SectionCard("Subscription", "status=${ui.subscription?.status ?: "-"} plan=${ui.subscription?.planId ?: "-"}")
        SectionCard("Quota", "messages=${ui.usage?.aiMessages ?: "-"} tokens=${ui.usage?.totalTokens ?: "-"} storage=${ui.usage?.storageBytes ?: "-"}")
        Text("Plans", style = MaterialTheme.typography.titleLarge)
        LazyColumn {
            items(ui.plans) { p -> SectionCard(p.name ?: p.code ?: "Plan", "${p.price ?: 0} ${p.currency ?: ""} · max agents ${p.maxAgents ?: "-"}") }
            item { Text("Invoices", style = MaterialTheme.typography.titleLarge) }
            items(ui.invoices) { inv -> SectionCard(inv.invoiceNumber ?: inv.id ?: "Invoice", "${inv.amount ?: 0} ${inv.currency ?: ""} · ${inv.status}") }
        }
    }
}
''')

w("app/src/main/java/com/thtwaat/starter/ui/settings/SettingsScreen.kt", r'''
package com.thtwaat.starter.ui.settings

import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.thtwaat.starter.core.datastore.SessionStore
import com.thtwaat.starter.core.util.Result
import com.thtwaat.starter.data.remote.dto.UserProfileDto
import com.thtwaat.starter.data.repository.AuthRepository
import com.thtwaat.starter.ui.components.ErrorText
import com.thtwaat.starter.ui.components.ScreenPadding
import com.thtwaat.starter.ui.components.SectionCard
import com.thtwaat.starter.ui.components.SimpleField
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val authRepository: AuthRepository,
    private val sessionStore: SessionStore,
) : ViewModel() {
    val themeMode = sessionStore.themeMode.stateIn(viewModelScope, SharingStarted.Eagerly, "system")
    private val _profile = MutableStateFlow<UserProfileDto?>(null)
    val profile = _profile.asStateFlow()
    private val _error = MutableStateFlow<String?>(null)
    val error = _error.asStateFlow()

    init {
        viewModelScope.launch {
            when (val r = authRepository.me()) {
                is Result.Success -> _profile.value = r.data
                is Result.Error -> _error.value = r.message
            }
        }
    }

    fun setTheme(mode: String) = viewModelScope.launch { sessionStore.setTheme(mode) }
    fun saveApiKey(key: String) = viewModelScope.launch { sessionStore.saveApiKey(key) }
    fun logout(onDone: () -> Unit) = viewModelScope.launch {
        authRepository.logout()
        onDone()
    }
}

@Composable
fun SettingsScreen(onLoggedOut: () -> Unit, vm: SettingsViewModel = hiltViewModel()) {
    val profile by vm.profile.collectAsState()
    val theme by vm.themeMode.collectAsState()
    val error by vm.error.collectAsState()
    var apiKey by remember { mutableStateOf("") }
    ScreenPadding {
        Text("Settings", style = MaterialTheme.typography.headlineMedium)
        ErrorText(error)
        SectionCard(
            "Profile",
            "${profile?.firstName ?: ""} ${profile?.lastName ?: ""}\n${profile?.email ?: "-"}\nrole=${profile?.role ?: "-"}",
        )
        SectionCard("Company", "company_id=${profile?.companyId ?: "-"}")
        Text("Theme: $theme")
        TextButton(onClick = { vm.setTheme("system") }) { Text("System") }
        TextButton(onClick = { vm.setTheme("light") }) { Text("Light") }
        TextButton(onClick = { vm.setTheme("dark") }) { Text("Dark") }
        SimpleField(apiKey, { apiKey = it }, "Agent API key")
        Button(onClick = { vm.saveApiKey(apiKey) }) { Text("Save API key") }
        Button(onClick = { vm.logout(onLoggedOut) }) { Text("Logout") }
    }
}
''')

print("remaining screens done")
