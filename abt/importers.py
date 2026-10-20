"""Import external network specifications into the ABT `Network` model.

Supports two schemas observed in the multi-host benchmarks used by the red-team
tools this project targets:

  * MHBench-generated environments (subnets -> hosts -> per-host vulnerability
    "playbooks", subnet-level connectivity, data_exfiltration/host_access goals).
  * APT-Agent topology specs (hosts by IP/role, CVSS-scored service edges with a
    Metasploit module name, a single goal host).

Neither schema is redistributed here; only the (documented, publicly described)
JSON shape is read. Defaults used to fill in information the source schema does
not provide (exploit probability, impact, asset value) are called out explicitly
and should be calibrated against real data before being used for paper results.
"""
from __future__ import annotations

import json
from dataclasses import replace
from typing import Dict, List, Tuple

from .harm import ATTACKER
from .model import Asset, AttackGoal, Host, LegitFlow, Network, Service, Vuln

# --------------------------------------------------------------------------- #
# MHBench
# --------------------------------------------------------------------------- #

# MHBench vulnerability "playbooks" carry no explicit probability/impact; these
# defaults are placeholders pending calibration against MHBench's own experiment
# logs (see README/PROGRESS.md "known limitations").
MHBENCH_DEFAULT_P = 0.6
MHBENCH_DEFAULT_IMPACT = 6.0
MHBENCH_DEFAULT_ASSET_VALUE = 10.0


def load_mhbench(path: str,
                  default_p: float = MHBENCH_DEFAULT_P,
                  default_impact: float = MHBENCH_DEFAULT_IMPACT,
                  default_asset_value: float = MHBENCH_DEFAULT_ASSET_VALUE
                  ) -> Tuple[Network, List[AttackGoal]]:
    """Parse an MHBench-generated environment JSON file into (Network, goals).

    Hosts are keyed by IP address (MHBench's natural identifier). Each distinct
    vulnerability "playbook" seen on a host becomes a synthetic Service/Vuln pair
    on a locally-assigned port, since MHBench models exploits as idempotent
    Ansible playbooks rather than CVE/port pairs. Hosts whose subnet already has
    a privilege_escalation playbook have their incoming lateral-movement vulns
    upgraded to grant "root", approximating "land a foothold, then escalate
    locally" without needing self-loop edges in the attack graph.
    """
    with open(path) as f:
        data = json.load(f)
    return _mhbench_from_dict(data, default_p, default_impact, default_asset_value)


def _mhbench_from_dict(data: dict, default_p: float, default_impact: float,
                        default_asset_value: float) -> Tuple[Network, List[AttackGoal]]:
    hosts: Dict[str, Host] = {}
    subnet_of: Dict[str, str] = {}
    external: Dict[str, bool] = {}
    subnet_hosts: Dict[str, List[str]] = {}

    for net_spec in data.get("networks", []):
        for subnet in net_spec.get("subnets", []):
            sname = subnet["name"]
            subnet_hosts.setdefault(sname, [])
            for h in subnet.get("hosts", []):
                ip = h["ip_address"]
                hosts[ip] = Host(ip, sname)
                hosts[ip].services[0] = Service("base", 0, [])  # base reachability surface
                subnet_of[ip] = sname
                external[ip] = bool(subnet.get("external", False))
                subnet_hosts[sname].append(ip)

    flows = set()
    for conn in data.get("subnet_connections", []):
        a_hosts = subnet_hosts.get(conn["from_subnet"], [])
        b_hosts = subnet_hosts.get(conn["to_subnet"], [])
        for a in a_hosts:
            for b in b_hosts:
                flows.add((a, b, 0))
                if conn.get("bidirectional", True):
                    flows.add((b, a, 0))

    entry_points = [ip for ip, ext in external.items() if ext]

    # Synthesise one Service/Vuln per distinct vulnerability playbook on a host.
    port_counter: Dict[str, int] = {}
    seen_playbooks = set()
    privesc_hosts = set()
    for net_spec in data.get("networks", []):
        for subnet in net_spec.get("subnets", []):
            for hd in subnet.get("hosts", []):
                ip = hd["ip_address"]
                for v in hd.get("vulnerabilities", []):
                    key = (ip, v["playbook_path"])
                    if key in seen_playbooks:
                        continue
                    seen_playbooks.add(key)
                    port_counter[ip] = port_counter.get(ip, 0) + 1
                    port = 1000 + port_counter[ip]
                    is_privesc = v.get("type") == "privilege_escalation"
                    if is_privesc:
                        privesc_hosts.add(ip)
                    grants = "root" if (is_privesc or v.get("to_user") == "root") else "user"
                    cve = v["playbook_path"].rsplit("/", 1)[-1].rsplit(".", 1)[0]
                    hosts[ip].services[port] = Service(
                        cve, port, [Vuln(cve, default_p, default_impact, grants)])

                    src = v.get("from_host_ip") or ""
                    if src in ("", "None"):
                        if ip in entry_points:
                            src = ATTACKER
                        else:
                            src = None  # local-only (e.g. privesc chained off an existing foothold)
                    if src:
                        flows.add((src, ip, port))

    # Upgrade lateral-movement vulns on hosts that also carry a local privesc
    # playbook: once an attacker lands a user foothold there, they can chain to root.
    for ip in privesc_hosts:
        for svc in hosts[ip].services.values():
            svc.vulns = [replace(v, grants="root") if v.grants == "user" else v
                         for v in svc.vulns]

    assets: List[Asset] = []
    goals: List[AttackGoal] = []
    for g in data.get("goals", []):
        host_ip = g.get("host_ip")
        if not host_ip or host_ip not in hosts:
            continue
        asset_name = f"asset@{host_ip}"
        assets.append(Asset(asset_name, host_ip, default_asset_value))
        kind = "exfiltrate" if g.get("type") == "data_exfiltration" else "escalate"
        goals.append(AttackGoal(kind, host_ip, "user", asset_name))

    legit_flows = [LegitFlow(f"{a}->{b}", a, b, 0, 1.0) for (a, b, p) in flows if p == 0]

    network = Network(hosts=hosts, flows=flows, assets=assets,
                       legit_flows=legit_flows, entry_points=entry_points)
    return network, goals


# --------------------------------------------------------------------------- #
# APT-Agent topology schema
# --------------------------------------------------------------------------- #

APTAGENT_DEFAULT_ASSET_VALUE = 10.0


def load_apt_agent_topology(path: str,
                             default_asset_value: float = APTAGENT_DEFAULT_ASSET_VALUE
                             ) -> Tuple[Network, List[AttackGoal]]:
    """Parse an APT-Agent topology JSON file into (Network, goals).

    Hosts are keyed by IP (APT-Agent's `hosts[].id`). Each edge becomes a
    Service/Vuln on the destination host plus a permitted flow; edges whose
    `src` is the literal string "attacker" mark the destination as an entry
    point. Exploit-success probability is derived from the CVSS score
    (p = cvss / 10), a convenience mapping that should be validated against real
    data rather than assumed to be calibrated.
    """
    with open(path) as f:
        data = json.load(f)
    return _apt_agent_from_dict(data, default_asset_value)


def _apt_agent_from_dict(data: dict, default_asset_value: float) -> Tuple[Network, List[AttackGoal]]:
    hosts: Dict[str, Host] = {}
    for h in data.get("hosts", []):
        hid = h["id"]
        hosts[hid] = Host(hid, h.get("role", ""))

    flows = set()
    entry_points: List[str] = []
    port_counter: Dict[str, int] = {}
    for e in data.get("edges", []):
        src, dst, port = e["src"], e["dst"], e.get("port")
        if dst not in hosts:
            continue
        if src == ATTACKER:
            if dst not in entry_points:
                entry_points.append(dst)
        if port is None:
            port_counter[dst] = port_counter.get(dst, 0) + 1
            port = 2000 + port_counter[dst]
        cvss = float(e.get("cvss", 5.0))
        impact = float(e.get("impact", cvss))
        cve = e.get("exploit", f"vuln@{dst}:{port}")
        vuln = Vuln(cve, min(1.0, max(0.0, cvss / 10.0)), impact, "user")
        if port in hosts[dst].services:
            hosts[dst].services[port].vulns.append(vuln)
        else:
            hosts[dst].services[port] = Service(e.get("service", cve), port, [vuln])
        flows.add((src, dst, port))

    goal_id = data.get("goal")
    goals: List[AttackGoal] = []
    assets: List[Asset] = []
    if goal_id and goal_id in hosts:
        asset_name = f"asset@{goal_id}"
        assets.append(Asset(asset_name, goal_id, default_asset_value))
        goals.append(AttackGoal("exfiltrate", goal_id, "user", asset_name))

    # APT-Agent topologies don't describe legitimate-user traffic; default to no
    # workload, so availability constraints are vacuously satisfied until the
    # caller supplies real legit_flows for the environment being tested.
    network = Network(hosts=hosts, flows=flows, assets=assets,
                       legit_flows=[], entry_points=entry_points)
    return network, goals


# --------------------------------------------------------------------------- #
# Dispatch
# --------------------------------------------------------------------------- #

def load_network(path: str) -> Tuple[Network, List[AttackGoal]]:
    """Auto-detect schema (MHBench vs. APT-Agent topology) and import it."""
    with open(path) as f:
        data = json.load(f)
    if "hosts" in data and "edges" in data:
        return _apt_agent_from_dict(data, APTAGENT_DEFAULT_ASSET_VALUE)
    if "networks" in data:
        return _mhbench_from_dict(data, MHBENCH_DEFAULT_P, MHBENCH_DEFAULT_IMPACT,
                                   MHBENCH_DEFAULT_ASSET_VALUE)
    raise ValueError("Unrecognised network specification schema")
