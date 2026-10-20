"""Synthetic-fixture tests for MHBench / APT-Agent schema importers.

The fixtures below are written directly against the documented schemas (field
names, nesting) observed in MHBench-generated environments and in APT-Agent's
topology specification; no files from those repositories are copied here.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from abt.harm import attack_paths, goal_probability
from abt.importers import load_apt_agent_topology, load_mhbench, load_network

MHBENCH_FIXTURE = {
    "name": "mini",
    "networks": [{"name": "n", "subnets": [
        {"name": "subnet_0", "cidr": "10.0.0.0/24", "external": True, "hosts": [
            {"id": "h0", "name": "web", "ip_address": "10.0.0.10", "users": [],
             "vulnerabilities": [
                 {"type": "lateral_movement",
                  "playbook_path": "vulnerabilities/apacheStruts/setupStruts.yml",
                  "merge_strategy": "by_host", "internal_only": False,
                  "from_host_ip": "None", "to_host_ip": "10.0.0.10",
                  "from_user": "root", "to_user": "root"}],
             "is_attacker": False, "is_decoy": False}]},
        {"name": "subnet_1", "cidr": "10.0.1.0/24", "external": False, "hosts": [
            {"id": "h1", "name": "db", "ip_address": "10.0.1.10", "users": [],
             "vulnerabilities": [
                 {"type": "lateral_movement",
                  "playbook_path": "vulnerabilities/NetcatShell.yml",
                  "merge_strategy": "by_host", "internal_only": False,
                  "from_host_ip": "10.0.0.10", "to_host_ip": "10.0.1.10",
                  "from_user": "user", "to_user": "user"},
                 {"type": "privilege_escalation",
                  "playbook_path": "vulnerabilities/privledge_escalation/writeablePasswd/writeablePasswd.yml",
                  "merge_strategy": "by_host", "internal_only": False,
                  "from_host_ip": "", "to_host_ip": "10.0.1.10",
                  "from_user": "", "to_user": ""}],
             "is_attacker": False, "is_decoy": False}]}]}],
    "subnet_connections": [
        {"from_subnet": "subnet_0", "to_subnet": "subnet_1",
         "bidirectional": True, "protocol": None, "ports": None}],
    "goals": [
        {"type": "data_exfiltration", "target_host_id": "x", "target_user_id": "y",
         "playbook_path": "goals/data/addData.yml", "host_ip": "10.0.1.10",
         "src_path": "data.json", "dst_path": "/root/data.json", "host_user": "root"}],
}

APT_AGENT_FIXTURE = {
    "hosts": [{"id": "172.0.0.10", "role": "web"},
              {"id": "172.0.0.20", "role": "db-goal"}],
    "edges": [
        {"src": "attacker", "dst": "172.0.0.10", "port": 80, "service": "http",
         "cvss": 9.8, "exploit": "multi/http/test"},
        {"src": "172.0.0.10", "dst": "172.0.0.20", "port": 5432, "service": "postgresql",
         "cvss": 8.0, "exploit": "linux/postgres/test"}],
    "goal": "172.0.0.20",
}


def _write(fixture):
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump(fixture, f)
    f.close()
    return f.name


def test_load_mhbench_builds_reachable_goal():
    path = _write(MHBENCH_FIXTURE)
    try:
        net, goals = load_mhbench(path)
        assert set(net.hosts) == {"10.0.0.10", "10.0.1.10"}
        assert net.entry_points == ["10.0.0.10"]
        assert len(goals) == 1 and goals[0].host == "10.0.1.10"
        paths = attack_paths(net, goals[0])
        assert paths and paths[0].hosts == ["attacker", "10.0.0.10", "10.0.1.10"]
        assert goal_probability(net, goals[0]) > 0
    finally:
        os.unlink(path)


def test_load_apt_agent_topology_builds_reachable_goal():
    path = _write(APT_AGENT_FIXTURE)
    try:
        net, goals = load_apt_agent_topology(path)
        assert set(net.hosts) == {"172.0.0.10", "172.0.0.20"}
        assert net.entry_points == ["172.0.0.10"]
        assert len(goals) == 1 and goals[0].host == "172.0.0.20"
        assert goal_probability(net, goals[0]) > 0
    finally:
        os.unlink(path)


def test_load_network_dispatches_by_schema():
    mb_path, apt_path = _write(MHBENCH_FIXTURE), _write(APT_AGENT_FIXTURE)
    try:
        net_mb, _ = load_network(mb_path)
        net_apt, _ = load_network(apt_path)
        assert len(net_mb.hosts) == 2
        assert len(net_apt.hosts) == 2
    finally:
        os.unlink(mb_path)
        os.unlink(apt_path)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
