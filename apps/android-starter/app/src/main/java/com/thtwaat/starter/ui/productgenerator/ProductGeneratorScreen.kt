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
