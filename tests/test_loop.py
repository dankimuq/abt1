import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from abt.loop import TrainingLoop
from abt.master import MasterAgent
from abt.red import AttackResult, RedTeamAdapter
from examples.enterprise import build


class AlwaysSuccessfulAttacker(RedTeamAdapter):
    name = "always-successful"

    def __init__(self, goals):
        self._goals = goals

    def goals(self):
        return self._goals

    def run(self, net, rng):
        return AttackResult(True, ["attacker", "web", "app", "db"], self._goals[0])


class LegacyBooleanAttacker(AlwaysSuccessfulAttacker):
    def run(self, net, rng):
        return True


def test_training_loop_records_rounds_and_converges():
    net, goals = build()
    loop = TrainingLoop(
        MasterAgent(net, goals),
        AlwaysSuccessfulAttacker(goals),
        detect_p=1.0,
        seed=3,
        convergence_patience=1,
    )

    result = loop.run(rounds=5)

    assert result.converged
    assert len(result.rounds) < 5
    assert result.rounds[0].attack.success
    assert result.rounds[0].detected_hosts == ["web", "app"]
    assert result.rounds[0].after.risk <= result.rounds[0].before.risk
    assert result.rounds[-1].cumulative_success_rate == 1.0
    assert result.success_rate == 1.0


def test_training_loop_runs_requested_rounds_when_convergence_not_reached():
    net, goals = build()
    loop = TrainingLoop(
        MasterAgent(net, goals),
        AlwaysSuccessfulAttacker(goals),
        detect_p=0.0,
        max_actions=0,
        convergence_patience=2,
    )

    result = loop.run(rounds=3)

    assert result.converged
    assert len(result.rounds) == 2
    assert not result.rounds[0].detected_hosts
    assert result.success_rate == 1.0


def test_training_loop_accepts_legacy_boolean_attackers():
    net, goals = build()
    loop = TrainingLoop(
        MasterAgent(net, goals),
        LegacyBooleanAttacker(goals),
        detect_p=1.0,
        max_actions=0,
        convergence_patience=1,
    )

    result = loop.run(rounds=1)

    assert result.rounds[0].attack.success
    assert result.success_rate == 1.0
