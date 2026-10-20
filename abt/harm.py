"""Step 4/5: network-wide attack graph (two-layer HARM) with goal capture.

Upper layer: host-level attack graph (attacker -> hosts via permitted flows).
Lower layer: per-host attack tree (noisy-OR over exploitable vulnerabilities).
Host-level defences (MIR, diversity, IP shuffling) scale exploit probability.
Hosts already known to be compromised (MIR alerts) are extra start nodes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .model import AttackGoal, Network, PRIV

ATTACKER = "attacker"

# Multiplicative reductions of exploit success on a host. Calibrate per paper/experiment.
MIR_BLOCK = 0.6        # P(MIR detects AND contains an exploitation step)
DIVERSITY_FACTOR = 0.7
SHUFFLE_FACTOR = 0.6


def host_factor(net: Network, h: str) -> float:
    host = net.hosts[h]
    f = 1.0
    if host.mir:
        f *= 1 - MIR_BLOCK
    if host.diversified:
        f *= DIVERSITY_FACTOR
    if host.ip_shuffled:
        f *= SHUFFLE_FACTOR
    return f


def host_p(net: Network, h: str, port: int, min_priv: str = "user") -> float:
    """Lower layer: noisy-OR of exploitable vulns on one service."""
    svc = net.hosts[h].services.get(port)
    if not svc or not svc.enabled:
        return 0.0
    q = 1.0
    for v in svc.vulns:
        if PRIV[v.grants] >= PRIV[min_priv]:
            q *= 1 - v.p
    return (1 - q) * host_factor(net, h)


def edge_p(net: Network, flows, src: str, dst: str, min_priv: str = "user") -> float:
    q = 1.0
    for (s, d, port) in flows:
        if s == src and d == dst:
            q *= 1 - host_p(net, dst, port, min_priv)
    return 1 - q


@dataclass
class AttackPath:
    hosts: List[str]
    asp: float      # attack success probability


def attack_paths(net: Network, goal: AttackGoal, max_len: int = 6) -> List[AttackPath]:
    flows = set(net.flows)
    for e in net.entry_points:
        for port in net.hosts[e].services:
            flows.add((ATTACKER, e, port))
    succ: Dict[str, List[str]] = {}
    for s, d, _ in flows:
        if d in net.hosts and d not in succ.setdefault(s, []):
            succ[s].append(d)

    out: List[AttackPath] = []

    def dfs(node: str, path: List[str], prob: float, seen: set):
        for nxt in succ.get(node, []):
            if nxt in seen:
                continue
            last = nxt == goal.host
            p = edge_p(net, flows, node, nxt, goal.min_priv if last else "user")
            if p <= 0:
                continue
            if last:
                out.append(AttackPath(path + [nxt], prob * p))
            elif len(path) < max_len:
                dfs(nxt, path + [nxt], prob * p, seen | {nxt})

    dfs(ATTACKER, [ATTACKER], 1.0, {ATTACKER})
    for c in net.compromised:
        if c == goal.host:
            out.append(AttackPath([c], 1.0))   # goal already achieved
        elif c in net.hosts:
            dfs(c, [c], 1.0, {c})
    return sorted(out, key=lambda p: -p.asp)


def goal_probability(net: Network, goal: AttackGoal) -> float:
    q = 1.0
    for p in attack_paths(net, goal):
        q *= 1 - p.asp
    return 1 - q


def risk(net: Network, goals: List[AttackGoal]) -> float:
    """Value-weighted probability of goal achievement, in [0,1]."""
    tot = sum(net.asset_value(g) for g in goals) or 1.0
    return sum(net.asset_value(g) * goal_probability(net, g) for g in goals) / tot
