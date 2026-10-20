"""Step 1 + network model: assets, protection requirements, hosts, services, flows."""
from __future__ import annotations

import copy
import ipaddress
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

PRIV = {"none": 0, "user": 1, "root": 2}
Flow = Tuple[str, str, int]  # (src, dst, port)


@dataclass(frozen=True)
class Vuln:
    cve: str
    p: float                 # exploit success probability (e.g. from CVSS exploitability)
    impact: float = 5.0      # CVSS-like impact, used by HARM metrics
    grants: str = "user"     # privilege gained on the target host
    cost: float = 1.0        # attacker effort


@dataclass
class Service:
    name: str
    port: int
    vulns: List[Vuln] = field(default_factory=list)
    enabled: bool = True


@dataclass
class Host:
    name: str
    zone: str
    services: Dict[int, Service] = field(default_factory=dict)
    mir: bool = False          # MIR agent installed
    ip_shuffled: bool = False  # MTD: IP/port shuffling active
    diversified: bool = False  # MTD: software diversity active


@dataclass
class Asset:
    """Step 1: what to protect and the required protection."""
    name: str
    host: str
    value: float                       # business value (0-10)
    kind: str = "data"                 # data | service | privilege
    confidentiality: bool = True
    integrity: bool = True
    min_availability: float = 0.9      # required share of legit flows (touching the host) that must work
    min_performance: float = 0.8       # required performance factor of the hosting node


@dataclass
class LegitFlow:
    """Legitimate user workload that defence must not break."""
    name: str
    src: str
    dst: str
    port: int
    weight: float = 1.0


@dataclass
class AttackGoal:
    """Incalmo-style goal, e.g. exfiltrate data from host / gain root on host."""
    kind: str            # exfiltrate | escalate | disrupt
    host: str
    min_priv: str = "user"
    asset: str = ""


@dataclass
class SDNController:
    """Simulated SDN control-plane state; this is not a live controller adapter."""
    virtual_ips: Dict[str, str]
    address_pool: List[str]
    blocked_flows: Set[Flow] = field(default_factory=set)
    policy_updates: int = 0

    def __post_init__(self) -> None:
        if len(set(self.virtual_ips.values())) != len(self.virtual_ips):
            raise ValueError("SDN virtual IP assignments must be unique")
        if len(set(self.address_pool)) != len(self.address_pool):
            raise ValueError("SDN address pool entries must be unique")
        for address in set(self.virtual_ips.values()) | set(self.address_pool):
            ipaddress.ip_address(address)

    def can_shuffle(self, host: str) -> bool:
        current = self.virtual_ips.get(host)
        if current is None:
            return False
        in_use = set(self.virtual_ips.values())
        return any(address != current and address not in in_use for address in self.address_pool)

    def shuffle_host(self, host: str) -> str:
        current = self.virtual_ips.get(host)
        if current is None:
            raise ValueError(f"SDN controller has no virtual IP for host: {host}")
        in_use = set(self.virtual_ips.values())
        for address in self.address_pool:
            if address != current and address not in in_use:
                self.virtual_ips[host] = address
                self.policy_updates += 1
                return address
        raise ValueError(f"SDN address pool has no free address for host: {host}")

    def block_flow(self, flow: Flow) -> None:
        if flow not in self.blocked_flows:
            self.blocked_flows.add(flow)
            self.policy_updates += 1


@dataclass
class Network:
    hosts: Dict[str, Host]
    flows: Set[Flow]                   # currently permitted connectivity
    assets: List[Asset]
    legit_flows: List[LegitFlow]
    entry_points: List[str]            # hosts reachable from outside
    compromised: Set[str] = field(default_factory=set)  # learned from MIR alerts
    sdn_controller: Optional[SDNController] = None

    def clone(self) -> "Network":
        return copy.deepcopy(self)

    def asset_value(self, goal: AttackGoal) -> float:
        for a in self.assets:
            if a.name == goal.asset or (not goal.asset and a.host == goal.host):
                return a.value
        return 1.0
