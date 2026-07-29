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
    Column(modifier = Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
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
