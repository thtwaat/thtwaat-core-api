import SwiftUI

struct BillingView: View {
    @EnvironmentObject private var deps: AppDependencies
    @State private var plans: [Plan] = []
    @State private var invoices: [Invoice] = []
    @State private var subscription: Subscription?
    @State private var usage: UsageSnapshot?
    @State private var error: String?

    var body: some View {
        List {
            if let error { Text(error).foregroundStyle(.red) }
            Section("Current plan") {
                Text("status=\(subscription?.status ?? "-")")
                Text("plan=\(subscription?.planId ?? "-")")
            }
            Section("Quota / usage") {
                Text("messages=\(usage?.aiMessages ?? 0)")
                Text("tokens=\(usage?.totalTokens ?? 0)")
                Text("storage=\(usage?.storageBytes ?? 0)")
                Text("max agents=\(usage?.maxAgents ?? 0)")
            }
            Section("Plans") {
                ForEach(plans) { p in
                    VStack(alignment: .leading) {
                        Text(p.name ?? p.code ?? "Plan").font(.headline)
                        Text("\(p.price ?? 0) \(p.currency ?? "") · max agents \(p.maxAgents ?? 0)")
                    }
                }
            }
            Section("Invoices") {
                ForEach(invoices) { inv in
                    Text("\(inv.invoiceNumber ?? inv.id) · \(inv.amount ?? 0) \(inv.currency ?? "") · \(inv.status ?? "")")
                }
            }
        }
        .navigationTitle("Billing")
        .task {
            async let p = deps.billingRepository.plans()
            async let i = deps.billingRepository.invoices()
            async let s = deps.billingRepository.subscription()
            async let u = deps.usageRepository.current()
            if case .success(let list) = await p { plans = list }
            if case .success(let list) = await i { invoices = list }
            if case .success(let sub) = await s { subscription = sub }
            if case .success(let snap) = await u { usage = snap }
            if case .failure(let e) = await p { error = e.message }
        }
    }
}
