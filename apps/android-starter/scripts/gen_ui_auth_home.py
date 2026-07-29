from pathlib import Path
ROOT = Path(r"E:\THTWAAT\thtwaat-core-api\apps\android-starter")

def w(rel: str, content: str) -> None:
    path = ROOT / rel.replace("/", "\\")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.lstrip("\n"), encoding="utf-8", newline="\n")
    print("wrote", rel)

w("app/src/main/java/com/thtwaat/starter/ui/auth/AuthViewModel.kt", r'''
package com.thtwaat.starter.ui.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.thtwaat.starter.core.util.Result
import com.thtwaat.starter.data.repository.AuthRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

data class AuthUiState(
    val loading: Boolean = false,
    val error: String? = null,
    val message: String? = null,
)

@HiltViewModel
class AuthViewModel @Inject constructor(
    private val repo: AuthRepository,
) : ViewModel() {
    val isLoggedIn = repo.isLoggedIn.stateIn(viewModelScope, SharingStarted.Eagerly, false)
    private val _ui = MutableStateFlow(AuthUiState())
    val ui: StateFlow<AuthUiState> = _ui.asStateFlow()

    fun login(email: String, password: String, onSuccess: () -> Unit) = viewModelScope.launch {
        _ui.value = AuthUiState(loading = true)
        when (val r = repo.login(email.trim(), password)) {
            is Result.Success -> { _ui.value = AuthUiState(); onSuccess() }
            is Result.Error -> _ui.value = AuthUiState(error = r.message)
        }
    }

    fun signup(email: String, password: String, first: String, last: String, onSuccess: () -> Unit) = viewModelScope.launch {
        _ui.value = AuthUiState(loading = true)
        when (val r = repo.signup(email.trim(), password, first, last)) {
            is Result.Success -> {
                when (val login = repo.login(email.trim(), password)) {
                    is Result.Success -> { _ui.value = AuthUiState(message = "Account created"); onSuccess() }
                    is Result.Error -> _ui.value = AuthUiState(message = "Created. Please login.", error = login.message)
                }
            }
            is Result.Error -> _ui.value = AuthUiState(error = r.message)
        }
    }

    fun forgot(email: String) = viewModelScope.launch {
        _ui.value = AuthUiState(loading = true)
        when (val r = repo.forgotPassword(email.trim())) {
            is Result.Success -> _ui.value = AuthUiState(message = "Reset email sent if account exists")
            is Result.Error -> _ui.value = AuthUiState(error = r.message)
        }
    }

    fun logout(onDone: () -> Unit) = viewModelScope.launch {
        repo.logout()
        onDone()
    }
}
''')

w("app/src/main/java/com/thtwaat/starter/ui/auth/AuthScreens.kt", r'''
package com.thtwaat.starter.ui.auth

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
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
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.thtwaat.starter.ui.components.ErrorText
import com.thtwaat.starter.ui.components.SimpleField
import androidx.compose.material3.OutlinedTextField

@Composable
fun LoginScreen(
    onSignup: () -> Unit,
    onForgot: () -> Unit,
    onLoggedIn: () -> Unit,
    vm: AuthViewModel = hiltViewModel(),
) {
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    val ui by vm.ui.collectAsState()
    Column(Modifier = Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("THTWAAT", style = MaterialTheme.typography.displaySmall)
        Text("Sign in to your AI workspace", style = MaterialTheme.typography.bodyLarge)
        SimpleField(email, { email = it }, "Email")
        OutlinedTextField(
            value = password,
            onValueChange = { password = it },
            label = { Text("Password") },
            visualTransformation = PasswordVisualTransformation(),
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
        )
        ErrorText(ui.error)
        Button(onClick = { vm.login(email, password, onLoggedIn) }, enabled = !ui.loading, modifier = Modifier.fillMaxWidth()) {
            Text(if (ui.loading) "Signing in..." else "Login")
        }
        TextButton(onClick = onForgot) { Text("Forgot password?") }
        TextButton(onClick = onSignup) { Text("Create account") }
    }
}

@Composable
fun SignupScreen(onBack: () -> Unit, onDone: () -> Unit, vm: AuthViewModel = hiltViewModel()) {
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var first by remember { mutableStateOf("") }
    var last by remember { mutableStateOf("") }
    val ui by vm.ui.collectAsState()
    Column(modifier = Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Create account", style = MaterialTheme.typography.headlineMedium)
        SimpleField(first, { first = it }, "First name")
        SimpleField(last, { last = it }, "Last name")
        SimpleField(email, { email = it }, "Email")
        OutlinedTextField(value = password, onValueChange = { password = it }, label = { Text("Password") }, visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth(), singleLine = true)
        ErrorText(ui.error)
        if (ui.message != null) Text(ui.message!!)
        Button(onClick = { vm.signup(email, password, first, last, onDone) }, enabled = !ui.loading, modifier = Modifier.fillMaxWidth()) { Text("Sign up") }
        TextButton(onClick = onBack) { Text("Back") }
    }
}

@Composable
fun ForgotPasswordScreen(onBack: () -> Unit, vm: AuthViewModel = hiltViewModel()) {
    var email by remember { mutableStateOf("") }
    val ui by vm.ui.collectAsState()
    Column(modifier = Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Forgot password", style = MaterialTheme.typography.headlineMedium)
        SimpleField(email, { email = it }, "Email")
        ErrorText(ui.error)
        if (ui.message != null) Text(ui.message!!)
        Button(onClick = { vm.forgot(email) }, enabled = !ui.loading, modifier = Modifier.fillMaxWidth()) { Text("Send reset") }
        TextButton(onClick = onBack) { Text("Back") }
    }
}
''')

w("app/src/main/java/com/thtwaat/starter/ui/home/HomeViewModel.kt", r'''
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
''')

w("app/src/main/java/com/thtwaat/starter/ui/home/HomeScreen.kt", r'''
package com.thtwaat.starter.ui.home

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.thtwaat.starter.ui.components.ErrorText
import com.thtwaat.starter.ui.components.LoadingBox
import com.thtwaat.starter.ui.components.ScreenPadding
import com.thtwaat.starter.ui.components.SectionCard

@Composable
fun HomeScreen(
    onOpenChat: () -> Unit,
    onOpenKnowledge: () -> Unit,
    onOpenProduct: () -> Unit,
    onOpenDomains: () -> Unit,
    onOpenBilling: () -> Unit,
    vm: HomeViewModel = hiltViewModel(),
) {
    val ui by vm.ui.collectAsState()
    if (ui.loading) {
        LoadingBox(); return
    }
    ScreenPadding {
        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxSize()) {
            item { Text("Dashboard", style = MaterialTheme.typography.headlineMedium) }
            item { ErrorText(ui.error) }
            item {
                SectionCard(
                    title = "Usage summary",
                    body = "Messages: ${ui.usage?.aiMessages ?: "-"} · Tokens: ${ui.usage?.totalTokens ?: "-"} · Agents max: ${ui.usage?.maxAgents ?: "-"}",
                    actionLabel = "Billing",
                    onAction = onOpenBilling,
                )
            }
            item {
                SectionCard(
                    title = "Analytics",
                    body = ui.analytics?.toString()?.take(180) ?: "No analytics yet",
                )
            }
            item { Text("Recent conversations", style = MaterialTheme.typography.titleLarge) }
            items(ui.conversations) { c ->
                SectionCard(title = c.id, body = "${c.messages.size} messages · ${c.updatedAt ?: c.createdAt ?: ""}", actionLabel = "Open chat", onAction = onOpenChat)
            }
            item { Text("Recent agents", style = MaterialTheme.typography.titleLarge) }
            items(ui.agents.take(5)) { a ->
                SectionCard(title = a.name, body = a.status ?: "unknown")
            }
            item {
                TextButton(onClick = onOpenKnowledge) { Text("Knowledge") }
                TextButton(onClick = onOpenProduct) { Text("Product Generator") }
                TextButton(onClick = onOpenDomains) { Text("Domains") }
                TextButton(onClick = { vm.refresh() }) { Text("Refresh") }
            }
        }
    }
}
''')

print("auth+home done")
