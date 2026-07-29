package com.thtwaat.starter.ui.chat

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.thtwaat.starter.core.util.MarkdownText
import com.thtwaat.starter.ui.components.ErrorText

@Composable
fun ChatScreen(vm: ChatViewModel = hiltViewModel()) {
    val ui by vm.ui.collectAsState()
    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        LazyColumn(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(ui.messages) { msg ->
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Text(msg.role.uppercase())
                        if (msg.role == "assistant") MarkdownText(msg.content) else Text(msg.content)
                    }
                }
            }
            if (ui.typing) item { Text("Assistant is typing...") }
        }
        ErrorText(ui.error)
        LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(vertical = 8.dp)) {
            items(ui.suggested) { s -> AssistChip(onClick = { vm.useSuggestion(s) }, label = { Text(s) }) }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
            OutlinedTextField(value = ui.input, onValueChange = vm::onInput, modifier = Modifier.weight(1f), label = { Text("Message") })
            Button(onClick = { vm.send(true) }, enabled = !ui.streaming) { Text("Send") }
        }
        Row {
            TextButton(onClick = vm::stop, enabled = ui.streaming) { Text("Stop") }
            TextButton(onClick = vm::retry, enabled = !ui.streaming) { Text("Retry") }
        }
    }
}
