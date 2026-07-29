package com.thtwaat.starter.ui.navigation

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Send
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
        Tab(Routes.Chat, "Chat", Icons.Default.Send),
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
