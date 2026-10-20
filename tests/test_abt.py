import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from abt import MasterAgent, goal_probability
from abt.actions import block_flow
from abt.simulator import Weights, evaluate
from examples.enterprise import build


def test_attack_paths_found():
    net, goals = build()
    assert all(goal_probability(net, g) > 0 for g in goals)


def test_blocking_legit_flow_hurts_availability_and_violates():
    net, goals = build()
    ev = evaluate(net, goals, [block_flow("app", "db", 3306)], Weights())
    assert ev.availability < 1 and not ev.feasible


def test_plan_reduces_risk_and_respects_constraints():
    net, goals = build()
    plan = MasterAgent(net, goals).plan()
    assert plan.after.risk < plan.before.risk
    assert plan.after.feasible


def test_alert_updates_world_model():
    net, goals = build()
    m = MasterAgent(net, goals)
    m.ingest({"type": "compromise", "host": "db"})
    assert goal_probability(m.net, goals[0]) == 1.0
