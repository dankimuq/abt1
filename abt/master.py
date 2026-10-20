"""Master agent: network-wide monitoring, planning, simulation and recommendation."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .actions import Action, candidate_actions
from .harm import attack_paths
from .model import AttackGoal, Network
from .red import ATTACKER, AttackResult
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

    def observe(
        self,
        result: AttackResult,
        detect_p: float = 0.6,
        rng: Optional[random.Random] = None,
    ) -> List[str]:
        if not 0.0 <= detect_p <= 1.0:
            raise ValueError("detect_p must be between 0 and 1")
        if not result.success:
            return []

        rng = rng or random.Random()
        goal_host = result.goal.host if result.goal else None
        detected = []
        for host in result.path:
            if host in (ATTACKER, goal_host):
                continue
            if host not in self.net.hosts:
                raise ValueError(f"attack path contains unknown host: {host}")
            if host not in self.net.compromised and rng.random() < detect_p:
                self.ingest({"type": "compromise", "host": host})
                detected.append(host)
        return detected

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
        """Apply a feasible plan to the in-memory model; no live controller is invoked."""
        if not plan.after.feasible:
            raise ValueError("cannot execute an infeasible defence plan")
        for a in plan.actions:
            a.apply(self.net)
