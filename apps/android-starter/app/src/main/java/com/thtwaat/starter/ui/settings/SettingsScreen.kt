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
