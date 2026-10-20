"""Steps 2 and 3: defence action catalogue.

Host-level actions are executed through the MIR agent (EDR-like); network-level
actions through the network controller (firewall/SDN, segmentation, service
composition, MTD). Each action is tagged with the kill-chain phase it targets so
the master agent can reason about defence-in-depth (MTD-in-depth style mapping).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List

from .model import Network

KILL_CHAIN = ["recon", "weaponize", "deliver", "exploit", "install", "c2", "objective"]


@dataclass
class Action:
    name: str
    level: str            # "host" (MIR) | "network"
    phase: str            # kill-chain phase targeted
    cost: float           # deployment/operational cost
    perf_overhead: float  # performance penalty on the affected host(s) (0-1)
    target: str           # primary host (for perf accounting), "" if network-wide
    apply: Callable[[Network], None]


def install_mir(h: str) -> Action:
    def f(n): n.hosts[h].mir = True
    return Action(f"mir:install@{h}", "host", "exploit", 1.0, 0.05, h, f)


def patch(h: str, port: int, cve: str) -> Action:
    def f(n):
        s = n.hosts[h].services[port]
        s.vulns = [v for v in s.vulns if v.cve != cve]
    return Action(f"mir:patch@{h}:{port}:{cve}", "host", "exploit", 2.0, 0.02, h, f)


def disable_service(h: str, port: int) -> Action:
    def f(n): n.hosts[h].services[port].enabled = False
    return Action(f"mir:disable@{h}:{port}", "host", "exploit", 0.5, 0.0, h, f)


def diversify(h: str) -> Action:
    def f(n): n.hosts[h].diversified = True
    return Action(f"mtd:diversify@{h}", "host", "weaponize", 3.0, 0.03, h, f)


def shuffle_ip(h: str) -> Action:
    def f(n):
        if n.sdn_controller is not None:
            n.sdn_controller.shuffle_host(h)
        n.hosts[h].ip_shuffled = True
    return Action(f"mtd:shuffle@{h}", "network", "recon", 1.5, 0.02, h, f)


def block_flow(s: str, d: str, port: int) -> Action:
    def f(n):
        flow = (s, d, port)
        if n.sdn_controller is not None:
            n.sdn_controller.block_flow(flow)
        n.flows.discard(flow)
    return Action(f"net:block@{s}->{d}:{port}", "network", "c2", 0.5, 0.0, "", f)


def isolate_host(h: str) -> Action:
    def f(n):
        blocked = {flow for flow in n.flows if h in (flow[0], flow[1])}
        if n.sdn_controller is not None:
            for flow in blocked:
                n.sdn_controller.block_flow(flow)
        n.flows.difference_update(blocked)
    return Action(f"mir:isolate@{h}", "host", "c2", 1.0, 0.0, h, f)


def candidate_actions(net: Network) -> List[Action]:
    acts: List[Action] = []
    for h, host in net.hosts.items():
        if not host.mir:
            acts.append(install_mir(h))
        if not host.diversified:
            acts.append(diversify(h))
        if not host.ip_shuffled and (
            net.sdn_controller is None or net.sdn_controller.can_shuffle(h)
        ):
            acts.append(shuffle_ip(h))
        for port, svc in host.services.items():
            if svc.enabled:
                acts.append(disable_service(h, port))
            for v in svc.vulns:
                acts.append(patch(h, port, v.cve))
    for (s, d, p) in sorted(net.flows):
        acts.append(block_flow(s, d, p))
    return acts
