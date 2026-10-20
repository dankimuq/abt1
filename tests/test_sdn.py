import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from abt.actions import block_flow, candidate_actions, shuffle_ip
from abt.model import SDNController
from abt.simulator import Weights, evaluate, simulate
from examples.enterprise import build


def _enable_sdn(net):
    net.sdn_controller = SDNController(
        virtual_ips={host: f"192.0.2.{index}" for index, host in enumerate(net.hosts, 10)},
        address_pool=[f"192.0.2.{index}" for index in range(100, 120)],
    )


def test_sdn_ip_shuffle_is_previewed_without_mutating_live_model():
    net, goals = build()
    _enable_sdn(net)
    original_ip = net.sdn_controller.virtual_ips["web"]
    action = shuffle_ip("web")

    before = evaluate(net, goals, [], Weights())
    after = evaluate(net, goals, [action], Weights())
    preview = simulate(net, [action])

    assert net.sdn_controller.virtual_ips["web"] == original_ip
    assert preview.sdn_controller.virtual_ips["web"] != original_ip
    assert preview.sdn_controller.policy_updates == 1
    assert after.sdn_policy_updates == 1
    assert after.sdn_address_changes == 1
    assert after.risk < before.risk
    assert after.availability == before.availability
    assert after.performance < before.performance


def test_sdn_flow_block_updates_policy_state_and_risk():
    net, goals = build()
    _enable_sdn(net)
    action = block_flow("web", "app", 8080)

    after = evaluate(net, goals, [action], Weights())
    preview = simulate(net, [action])

    assert ("web", "app", 8080) not in preview.flows
    assert ("web", "app", 8080) in preview.sdn_controller.blocked_flows
    assert after.sdn_policy_updates == 1
    assert after.risk < evaluate(net, goals, [], Weights()).risk
    assert net.sdn_controller.blocked_flows == set()


def test_sdn_shuffle_is_not_a_candidate_without_a_free_virtual_ip():
    net, _ = build()
    net.sdn_controller = SDNController(
        virtual_ips={host: f"192.0.2.{index}" for index, host in enumerate(net.hosts, 10)},
        address_pool=[],
    )

    assert not any(action.name == "mtd:shuffle@web" for action in candidate_actions(net))
