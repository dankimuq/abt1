"""Red-team side: goal spec / adapter interface for Incalmo, APT-Agent, AutoHacker,
and a Monte-Carlo attacker used to validate ABT plans without a live range.

Adapters translate each tool's goal into AttackGoal and its observed actions into
MIR-style events. Live integration is out of scope of this prototype.
"""
from __future__ import annotations

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

from .harm import ATTACKER, attack_paths
from .model import AttackGoal, Network


@dataclass
class AttackResult:
    success: bool
    path: List[str]
    goal: Optional[AttackGoal]

    def __bool__(self) -> bool:
        return self.success


class RedTeamAdapter(ABC):
    name = "abstract"

    @abstractmethod
    def goals(self) -> List[AttackGoal]: ...

    @abstractmethod
    def run(self, net: Network, rng: random.Random) -> AttackResult:
        """Attempt goals against net and report the result and successful path."""


class SimulatedAttacker(RedTeamAdapter):
    """Follows HARM paths best-first; each hop succeeds w.p. edge probability.
    `persistence` = number of alternative paths tried (Incalmo-like replanning)."""

    def __init__(self, goal_list: List[AttackGoal], name: str = "sim", persistence: int = 3):
        self.name, self._goals, self.persistence = name, goal_list, persistence

    def goals(self):
        return self._goals

    def run(self, net, rng):
        for g in self._goals:
            for path in attack_paths(net, g)[: self.persistence]:
                if rng.random() < path.asp:
                    return AttackResult(True, path.hosts, g)
        return AttackResult(False, [], None)


# Placeholders documenting where the real tools plug in.
class IncalmoAdapter(SimulatedAttacker):
    """TODO: map Incalmo high-level tasks/goals (e.g. exfiltrate data) <-> AttackGoal."""
    def __init__(self, goals): super().__init__(goals, "incalmo", persistence=4)


class APTAgentAdapter(SimulatedAttacker):
    """TODO: wrap APT-Agent LLM pen-test loop."""
    def __init__(self, goals): super().__init__(goals, "apt-agent", persistence=2)


class AutoHackerAdapter(SimulatedAttacker):
    """TODO: wrap AutoHacker."""
    def __init__(self, goals): super().__init__(goals, "autohacker", persistence=2)


def success_rate(net: Network, attacker: RedTeamAdapter, trials: int = 2000, seed: int = 1) -> float:
    rng = random.Random(seed)
    return sum(bool(attacker.run(net, rng)) for _ in range(trials)) / trials
