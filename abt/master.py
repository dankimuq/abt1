"""Master agent: network-wide monitoring, planning, simulation and recommendation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from .actions import Action, candidate_actions
from .harm import attack_paths
from .model import AttackGoal, Network
from .simulator import Evaluation, Weights, evaluate


@dataclass
class Plan:
    actions: List[Action]
    before: Evaluation
    after: Evaluation


class MasterAgent:
    def __init__(self, net: Network, goals: List[AttackGoal], weights: Weights = None):
        self.net, self.goals, self.w = net, goals, weights or Weights()
        self.mir_events: List[dict] = []

    # --- monitoring: ingest MIR alerts (Step 2) and update the world model ---
    def ingest(self, event: dict) -> None:
        self.mir_events.append(event)
        if event.get("type") == "compromise":
            self.net.compromised.add(event["host"])

    def attack_surface(self):
        return {g.host: attack_paths(self.net, g)[:5] for g in self.goals}

    # --- planning: greedy marginal-utility search over simulated actions ---
    def plan(self, max_actions: int = 10) -> Plan:
        chosen: List[Action] = []
        before = evaluate(self.net, self.goals, [], self.w)
        cur = before
        pool = candidate_actions(self.net)
        for _ in range(max_actions):
            best: Tuple[float, Action, Evaluation] = (0.0, None, None)  # type: ignore
            for a in pool:
                if a in chosen:
                    continue
                ev = evaluate(self.net, self.goals, chosen + [a], self.w)
                if not ev.feasible:
                    continue
                gain = ev.utility - cur.utility
                if gain > best[0] + 1e-9:
                    best = (gain, a, ev)
            if best[1] is None:
                break
            chosen.append(best[1])
            cur = best[2]
        return Plan(chosen, before, cur)

    def execute(self, plan: Plan) -> None:
        """Push approved actions to MIR agents / network controller (here: mutate the model)."""
        for a in plan.actions:
            a.apply(self.net)
