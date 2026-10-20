"""Multi-round attack, detection, and defence-planning loop."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional

from .master import MasterAgent, Plan
from .model import Network
from .red import AttackResult, RedTeamAdapter
from .simulator import Evaluation


@dataclass
class TrainingRound:
    number: int
    attack: AttackResult
    detected_hosts: List[str]
    plan: Plan
    cumulative_success_rate: float

    @property
    def before(self) -> Evaluation:
        return self.plan.before

    @property
    def after(self) -> Evaluation:
        return self.plan.after


@dataclass
class TrainingResult:
    rounds: List[TrainingRound]
    converged: bool
    initial_plan: Optional[Plan] = None

    @property
    def success_rate(self) -> float:
        if not self.rounds:
            return 0.0
        return sum(bool(round_.attack) for round_ in self.rounds) / len(self.rounds)


class TrainingLoop:
    def __init__(
        self,
        master: MasterAgent,
        attacker: RedTeamAdapter,
        detect_p: float = 0.6,
        max_actions: int = 10,
        seed: int = 1,
        convergence_patience: int = 2,
        proactive_actions: int = 0,
    ):
        if not 0.0 <= detect_p <= 1.0:
            raise ValueError("detect_p must be between 0 and 1")
        if max_actions < 0:
            raise ValueError("max_actions must be non-negative")
        if proactive_actions < 0:
            raise ValueError("proactive_actions must be non-negative")
        if convergence_patience < 1:
            raise ValueError("convergence_patience must be positive")
        self.master = master
        self.attacker = attacker
        self.detect_p = detect_p
        self.max_actions = max_actions
        self.proactive_actions = proactive_actions
        self.rng = random.Random(seed)
        self.convergence_patience = convergence_patience

    @property
    def net(self) -> Network:
        return self.master.net

    def run(self, rounds: int) -> TrainingResult:
        if rounds < 1:
            raise ValueError("rounds must be positive")

        history = []
        stable_rounds = 0
        successes = 0
        converged = False
        initial_plan = None
        if self.proactive_actions:
            initial_plan = self.master.plan(self.proactive_actions)
            self.master.execute(initial_plan)

        for number in range(1, rounds + 1):
            attack = self.attacker.run(self.net, self.rng)
            if isinstance(attack, bool):
                goals = self.attacker.goals()
                attack = AttackResult(attack, [], goals[0] if attack and goals else None)
            if not isinstance(attack, AttackResult):
                raise TypeError("attacker.run() must return AttackResult or bool")

            successes += bool(attack)
            detected_hosts = self.master.observe(attack, self.detect_p, self.rng)
            plan = self.master.plan(self.max_actions)
            self.master.execute(plan)
            history.append(
                TrainingRound(
                    number=number,
                    attack=attack,
                    detected_hosts=detected_hosts,
                    plan=plan,
                    cumulative_success_rate=successes / number,
                )
            )

            if not detected_hosts and not plan.actions:
                stable_rounds += 1
            else:
                stable_rounds = 0
            if stable_rounds >= self.convergence_patience:
                converged = True
                break

        return TrainingResult(history, converged, initial_plan)
