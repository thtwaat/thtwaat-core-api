from pathlib import Path
ROOT = Path(r"E:\THTWAAT\thtwaat-core-api\apps\android-starter")

def w(rel: str, content: str) -> None:
    path = ROOT / rel.replace("/", "\\")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.lstrip("\n"), encoding="utf-8", newline="\n")
    print("wrote", rel)

w("app/src/main/java/com/thtwaat/starter/core/util/MarkdownText.kt", r'''
package com.thtwaat.starter.core.util

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.sp

@Composable
fun MarkdownText(text: String) {
    val annotated = buildAnnotatedString {
        text.lines().forEachIndexed { index, line ->
            when {
                line.startsWith("### ") -> withStyle(SpanStyle(fontWeight = FontWeight.Bold, fontSize = 18.sp)) {
                    append(line.removePrefix("### ")); append('\n')
                }
                line.startsWith("## ") -> withStyle(SpanStyle(fontWeight = FontWeight.Bold, fontSize = 20.sp)) {
                    append(line.removePrefix("## ")); append('\n')
                }
                line.startsWith("# ") -> withStyle(SpanStyle(fontWeight = FontWeight.Bold, fontSize = 22.sp)) {
                    append(line.removePrefix("# ")); append('\n')
                }
                else -> {
                    var i = 0
                    while (i < line.length) {
                        when {
                            line.startsWith("**", i) -> {
                                val end = line.indexOf("**", i + 2)
                                if (end > i) {
                                    withStyle(SpanStyle(fontWeight = FontWeight.Bold)) { append(line.substring(i + 2, end)) }
                                    i = end + 2
                                } else {
                                    append(line[i]); i++
                                }
                            }
                            line.startsWith("`", i) -> {
                                val end = line.indexOf('`', i + 1)
                                if (end > i) {
                                    withStyle(SpanStyle(fontFamily = FontFamily.Monospace)) { append(line.substring(i + 1, end)) }
                                    i = end + 1
                                } else {
                                    append(line[i]); i++
                                }
                            }
                            else -> { append(line[i]); i++ }
                        }
                    }
                    if (index != text.lines().lastIndex) append('\n')
                }
            }
        }
    }
    Text(text = annotated, style = MaterialTheme.typography.bodyLarge)
}
''')

w("app/src/main/java/com/thtwaat/starter/ui/components/CommonUi.kt", r'''
package com.thtwaat.starter.ui.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
fun LoadingBox() {
    Column(
        modifier = Modifier.fillMaxSize(),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) { CircularProgressIndicator() }
}

@Composable
fun ErrorText(message: String?) {
    if (!message.isNullOrBlank()) {
        Text(text = message, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(8.dp))
    }
}

@Composable
fun SectionCard(title: String, body: String, actionLabel: String? = null, onAction: (() -> Unit)? = null) {
    Card(modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
        Column(Modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            Text(body, style = MaterialTheme.typography.bodyMedium)
            if (actionLabel != null && onAction != null) {
                Button(onClick = onAction) { Text(actionLabel) }
            }
        }
    }
}

@Composable
fun SimpleField(value: String, onChange: (String) -> Unit, label: String, modifier: Modifier = Modifier) {
    OutlinedTextField(
        value = value,
        onValueChange = onChange,
        label = { Text(label) },
        modifier = modifier.fillMaxWidth(),
        singleLine = true,
    )
}

@Composable
fun ScreenPadding(content: @Composable () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().padding(PaddingValues(16.dp)),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) { content() }
}
''')

w("app/src/main/java/com/thtwaat/starter/ui/navigation/Routes.kt", r'''
package com.thtwaat.starter.ui.navigation

object Routes {
    const val Splash = "splash"
    const val Login = "login"
    const val Signup = "signup"
    const val Forgot = "forgot"
    const val Home = "home"
    const val Chat = "chat"
    const val Knowledge = "knowledge"
    const val Agents = "agents"
    const val Marketplace = "marketplace"
    const val Product = "product"
    const val Domains = "domains"
    const val Billing = "billing"
    const val Settings = "settings"
}
''')

w("app/src/main/java/com/thtwaat/starter/ui/navigation/ThtwaatNavHost.kt", r'''
package com.thtwaat.starter.ui.navigation

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Chat
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.SmartToy
import androidx.compose.material.icons.filled.Store
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.thtwaat.starter.ui.agents.AgentsScreen
import com.thtwaat.starter.ui.auth.AuthViewModel
import com.thtwaat.starter.ui.auth.ForgotPasswordScreen
import com.thtwaat.starter.ui.auth.LoginScreen
import com.thtwaat.starter.ui.auth.SignupScreen
import com.thtwaat.starter.ui.billing.BillingScreen
import com.thtwaat.starter.ui.chat.ChatScreen
import com.thtwaat.starter.ui.domains.DomainsScreen
import com.thtwaat.starter.ui.home.HomeScreen
import com.thtwaat.starter.ui.knowledge.KnowledgeScreen
import com.thtwaat.starter.ui.marketplace.MarketplaceScreen
import com.thtwaat.starter.ui.productgenerator.ProductGeneratorScreen
import com.thtwaat.starter.ui.settings.SettingsScreen

private data class Tab(val route: String, val label: String, val icon: androidx.compose.ui.graphics.vector.ImageVector)

@Composable
fun ThtwaatNavHost(authVm: AuthViewModel = hiltViewModel()) {
    val navController = rememberNavController()
    val loggedIn by authVm.isLoggedIn.collectAsState(initial = false)
    val backStack by navController.currentBackStackEntryAsState()
    val current = backStack?.destination?.route

    LaunchedEffect(loggedIn) {
        if (loggedIn) {
            navController.navigate(Routes.Home) {
                popUpTo(Routes.Login) { inclusive = true }
            }
        }
    }

    val tabs = listOf(
        Tab(Routes.Home, "Home", Icons.Default.Home),
        Tab(Routes.Chat, "Chat", Icons.Default.Chat),
        Tab(Routes.Agents, "Agents", Icons.Default.SmartToy),
        Tab(Routes.Marketplace, "Market", Icons.Default.Store),
        Tab(Routes.Settings, "Settings", Icons.Default.Settings),
    )
    val showBottom = current in tabs.map { it.route } || current in listOf(Routes.Knowledge, Routes.Product, Routes.Domains, Routes.Billing)

    Scaffold(
        bottomBar = {
            if (showBottom) {
                NavigationBar {
                    tabs.forEach { tab ->
                        NavigationBarItem(
                            selected = current == tab.route,
                            onClick = {
                                navController.navigate(tab.route) {
                                    popUpTo(navController.graph.findStartDestination().id) { saveState = true }
                                    launchSingleTop = true
                                    restoreState = true
                                }
                            },
                            icon = { Icon(tab.icon, contentDescription = tab.label) },
                            label = { Text(tab.label) },
                        )
                    }
                }
            }
        },
    ) { padding ->
        NavHost(
            navController = navController,
            startDestination = if (loggedIn) Routes.Home else Routes.Login,
            modifier = Modifier.padding(padding),
        ) {
            composable(Routes.Login) {
                LoginScreen(
                    onSignup = { navController.navigate(Routes.Signup) },
                    onForgot = { navController.navigate(Routes.Forgot) },
                    onLoggedIn = { navController.navigate(Routes.Home) { popUpTo(Routes.Login) { inclusive = true } } },
                )
            }
            composable(Routes.Signup) {
                SignupScreen(onBack = { navController.popBackStack() }, onDone = { navController.popBackStack() })
            }
            composable(Routes.Forgot) {
                ForgotPasswordScreen(onBack = { navController.popBackStack() })
            }
            composable(Routes.Home) {
                HomeScreen(
                    onOpenChat = { navController.navigate(Routes.Chat) },
                    onOpenKnowledge = { navController.navigate(Routes.Knowledge) },
                    onOpenProduct = { navController.navigate(Routes.Product) },
                    onOpenDomains = { navController.navigate(Routes.Domains) },
                    onOpenBilling = { navController.navigate(Routes.Billing) },
                )
            }
            composable(Routes.Chat) { ChatScreen() }
            composable(Routes.Knowledge) { KnowledgeScreen() }
            composable(Routes.Agents) { AgentsScreen() }
            composable(Routes.Marketplace) { MarketplaceScreen() }
            composable(Routes.Product) { ProductGeneratorScreen() }
            composable(Routes.Domains) { DomainsScreen() }
            composable(Routes.Billing) { BillingScreen() }
            composable(Routes.Settings) {
                SettingsScreen(onLoggedOut = {
                    navController.navigate(Routes.Login) {
                        popUpTo(0) { inclusive = true }
                    }
                })
            }
        }
    }
}
''')

print("nav done")
