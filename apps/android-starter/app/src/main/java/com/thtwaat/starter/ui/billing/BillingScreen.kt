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
