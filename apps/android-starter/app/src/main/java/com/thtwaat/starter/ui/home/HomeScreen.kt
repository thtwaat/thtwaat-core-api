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
