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
