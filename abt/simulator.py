"""Defence simulation + multi-aspect evaluation (security, availability, performance, cost)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence

from .actions import Action
from .harm import risk
from .model import AttackGoal, Network


@dataclass
class Weights:
    security: float = 0.5
    availability: float = 0.25
    performance: float = 0.15
    cost: float = 0.10
    budget: float = 12.0


@dataclass
class Evaluation:
    risk: float
    availability: float
    performance: float
    cost: float
    utility: float
    violations: List[str] = field(default_factory=list)
    sdn_policy_updates: int = 0
    sdn_address_changes: int = 0

    @property
    def feasible(self) -> bool:
        return not self.violations


def _works(net: Network, f) -> bool:
    svc = net.hosts[f.dst].services.get(f.port)
    return (f.src, f.dst, f.port) in net.flows and bool(svc and svc.enabled)


def availability(net: Network, asset_host: str = "") -> float:
    flows = [f for f in net.legit_flows if not asset_host or asset_host in (f.src, f.dst)]
    tot = sum(f.weight for f in flows)
    return sum(f.weight for f in flows if _works(net, f)) / tot if tot else 1.0


def host_perf(overhead: Dict[str, float], h: str) -> float:
    return max(0.0, 1.0 - overhead.get(h, 0.0))


def simulate(net: Network, actions: Sequence[Action]) -> Network:
    """Apply actions to a copy; the real network is never touched until a plan is approved."""
    sim = net.clone()
    for a in actions:
        a.apply(sim)
    return sim


def evaluate(net: Network, goals: List[AttackGoal], actions: Sequence[Action], w: Weights) -> Evaluation:
    sim = simulate(net, actions)
    # state-based so that already-deployed agents keep costing performance
    overhead: Dict[str, float] = {}
    for h, host in sim.hosts.items():
        overhead[h] = 0.05 * host.mir + 0.03 * host.diversified + 0.02 * host.ip_shuffled
    for a in actions:
        if a.name.startswith("mir:patch"):
            overhead[a.target] = overhead.get(a.target, 0.0) + a.perf_overhead
    perf_asset = [host_perf(overhead, a.host) * a.value for a in net.assets]
    perf = sum(perf_asset) / (sum(a.value for a in net.assets) or 1.0)
    avail = sum(availability(sim, a.host) * a.value for a in net.assets) / (sum(a.value for a in net.assets) or 1.0)
    r = risk(sim, goals)
    cost = sum(a.cost for a in actions)
    policy_updates = 0
    address_changes = 0
    if sim.sdn_controller is not None:
        original_updates = net.sdn_controller.policy_updates if net.sdn_controller else 0
        policy_updates = sim.sdn_controller.policy_updates - original_updates
        if net.sdn_controller is not None:
            address_changes = sum(
                sim.sdn_controller.virtual_ips.get(host) != address
                for host, address in net.sdn_controller.virtual_ips.items()
            )

    violations = []
    for a in net.assets:
        if availability(sim, a.host) < a.min_availability:
            violations.append(f"availability<{a.min_availability} for {a.name}")
        if host_perf(overhead, a.host) < a.min_performance:
            violations.append(f"performance<{a.min_performance} for {a.name}")
    if cost > w.budget:
        violations.append("over budget")

    u = (w.security * (1 - r) + w.availability * avail + w.performance * perf
         - w.cost * min(1.0, cost / w.budget))
    return Evaluation(
        r, avail, perf, cost, u, violations,
        sdn_policy_updates=policy_updates,
        sdn_address_changes=address_changes,
    )
