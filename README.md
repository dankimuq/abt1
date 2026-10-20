# ABT – Automated Blue Teaming

ABT automatically defends a network against autonomous pen-testing agents (Incalmo, APT-Agent, AutoHacker). It extends the HARM-based security assessment framework (Enoch et al.) from *assessment* to closed-loop *defence*.

## 1. Architecture

```
          ┌────────────────────────── Master Agent ───────────────────────────┐
          │ ingest(events) → world model → HARM attack graph + goal capture    │
          │ candidate actions → simulate (copy of model) → evaluate → plan     │
          └───────▲───────────────────────────────┬───────────────────────────┘
        alerts/   │                               │ approved actions
        telemetry │                               ▼
   ┌──────────────┴───────────┐        ┌─────────────────────────────┐
   │ MIR agents (host level)  │        │ Network controller          │
   │ monitor/identify/respond │        │ topology, firewall/segments,│
   │ patch, kill, isolate     │        │ service composition, MTD    │
   └──────────────────────────┘        └─────────────────────────────┘
```

| Step | Requirement | Code |
|---|---|---|
| 1 | Asset inventory + required protection (C/I/A, min availability, min performance, legit workflows) | `Asset`, `LegitFlow` in `abt/model.py` |
| 2 | MIR agent (EDR-like host monitor/respond) | host actions `abt/actions.py`; alerts via `MasterAgent.ingest` |
| 3 | Network-level control (topology, connections, service composition) | `block_flow`, `shuffle_ip`, `disable_service` in `abt/actions.py` |
| 4 | Network-wide attack graph from topology, services, vulns, deployed controls | `abt/harm.py` (2-layer HARM: host graph + per-host noisy-OR attack trees) |
| 5 | Attacker goal (Incalmo-style) captured in graph | `AttackGoal`; `attack_paths(net, goal)` |
| 6 | Master agent: plan, simulate, evaluate, recommend | `abt/master.py`, `abt/simulator.py` |
| — | Import MHBench-generated / APT-Agent topology JSON into the `Network` model | `abt/importers.py` (`load_mhbench`, `load_apt_agent_topology`, `load_network`) |

## 2. Evaluation model

For a defence plan *A* applied to a **simulated copy** of the network:

- **Security**: risk = value-weighted P(goal) over goals, from HARM (noisy-OR across paths).
- **Availability**: weighted share of legitimate flows still working (per asset and overall).
- **Performance**: 1 − host overhead (MIR 0.05, diversity 0.03, shuffle 0.02, patch downtime 0.02; configurable).
- **Cost**: sum of action costs against a budget.
- **Utility** = w_s(1−risk) + w_a·avail + w_p·perf − w_c·cost/budget.
- **Hard constraints** (from Step 1): each asset's `min_availability`, `min_performance`, and the budget. Infeasible plans are rejected.

Planner: greedy marginal-utility selection (anytime, polynomial). Alternatives for the paper: beam search, ILP/MCTS, RL; compare against optimal on small networks.

## 3. SDN-aware network defense simulation

MTD does not inherently depend on SDN: address changes can be coordinated through
host firewalls, DHCP/DNS, VM/container networking, or NAT. ABT keeps MTD as a
separate defense family. For repeatable network-level policy experiments, the model
also supports an optional **simulated** `SDNController` with virtual-IP leases and
flow-block rules; it is not connected to a live SDN product. This SDN control-plane
emulation is the selected experimental assumption because it makes policy changes
and endpoint remapping explicit and measurable.

`MasterAgent.plan()` evaluates candidate actions on cloned networks first. A `Plan`
contains baseline and predicted security risk, legitimate-flow availability,
performance, cost, and SDN policy/address changes. `MasterAgent.execute(plan)`
applies a feasible plan to the in-memory model only. The `TrainingLoop` can apply a
proactive initial plan before the first simulated attack:

```python
from abt.loop import TrainingLoop
from abt.master import MasterAgent
from abt.model import SDNController
from abt.red import APTAgentAdapter
from examples.enterprise import build

net, goals = build()
net.sdn_controller = SDNController(
    virtual_ips={host: f"192.0.2.{index}" for index, host in enumerate(net.hosts, 10)},
    address_pool=[f"192.0.2.{index}" for index in range(100, 120)],
)
result = TrainingLoop(
    MasterAgent(net, goals), APTAgentAdapter(goals),
    proactive_actions=3, detect_p=0.6, seed=1,
).run(rounds=20)
print(result.initial_plan.after, result.success_rate)
```

This is control-plane emulation for isolated experiments. It does not program a
switch, firewall, or cloud security group. A future deployment adapter needs
dry-run, approval, state read-back, health checks, and rollback. See
[the network-defense design](slides/network-defense-design.md) for the bounded
proactive/reactive portfolio and deployment scope.

## 4. Attack-and-defence training loop

`abt.loop.TrainingLoop` runs repeated rounds against a `RedTeamAdapter`. Each round
records the attacker result and path, samples MIR detections for traversed hosts
(excluding the goal host), replans, executes the selected model actions, and stores
before/after evaluations. The loop stops early after a configurable number of
rounds with no newly detected hosts or defence actions.

```python
from abt.loop import TrainingLoop
from abt.master import MasterAgent
from abt.red import APTAgentAdapter
from examples.enterprise import build

net, goals = build()
result = TrainingLoop(
    MasterAgent(net, goals), APTAgentAdapter(goals), detect_p=0.6, seed=1
).run(rounds=20)
print(result.success_rate, result.converged)
```

## 5. Mapping asset → defence (kill-chain, per the MTD-in-depth paper)

Each `Action.phase` is tagged with a kill-chain phase (recon, weaponize, deliver, exploit, install, c2, objective). Current tags: IP shuffle→recon, diversity→weaponize, patch/MIR/disable→exploit, flow blocking/isolation→c2. **Please verify and refine this table against the paper's actual technique taxonomy**, then extend the catalogue (e.g., credential rotation, decoys, data encryption for the objective phase), and let the master prefer plans covering multiple phases for crown-jewel assets.

## 6. Red-team integration

`abt/red.py` defines `RedTeamAdapter`. The shipped adapters (Incalmo, APT-Agent, AutoHacker) are Monte-Carlo stand-ins with different persistence levels, so the pipeline is testable without a live range. For the paper, replace them with real runs in a testbed (e.g., Incalmo's range environment): translate each tool's goal into `AttackGoal` and its observed behaviour into MIR events.

## 7. Network-level defense roadmap (non-MTD)

Beyond MTD, the most direct next control is least-privilege segmentation using the
existing permitted-flow model. Egress filtering, DNS policy, network detections,
and graduated quarantine are follow-on controls; they require explicit external
destinations, DNS/telemetry state, and less coarse isolation semantics. ZTNA and
rate limiting need identity/context and traffic/QoS models that ABT does not yet
have. These are research/design proposals, not implemented controls.

See [the network-defense design](slides/network-defense-design.md) for the
source-grounded survey, model gaps, phased implementation sequence, and validation
metrics.

## 8. Suggested paper structure

1. Introduction – LLM-driven attackers (Incalmo, APT-Agent) outpace manual defence.
2. Background – HARM (HARMer), security models/metrics (Enoch 2021), MTD-in-depth.
3. ABT framework – the 6 components above; threat model; goal-aware attack graph.
4. Defence planning – utility formulation, constraints, algorithms.
5. Evaluation – RQ1: reduction in goal success vs. each attacker; RQ2: legit-user availability/performance cost; RQ3: planner optimality/scalability (hosts 10–1000); RQ4: reaction time to MIR alerts; ablations (host-only vs. network-only vs. both; with/without simulation).
6. Discussion – model fidelity, adaptive attackers, false positives, safety of autonomous response (human approval gate).

## 9. Known limitations / next steps

- Probabilities (MIR block 0.6, diversity 0.7, shuffle 0.6) are placeholders; calibrate with testbed data.
- Paths assume independence (noisy-OR over paths overestimates correlated paths).
- MIR is simulated; a real agent needs sensors (process, network, auth logs) and a signed command channel to the master.
- Network controller is a model mutation; add backends (iptables/SDN/cloud security groups).
- Attacker adaptation (re-planning after defence changes) is only approximated via `persistence`.

## 10. Run

```
python3 examples/run_demo.py
python3 -c 'import runpy; files=["tests/test_abt.py", "tests/test_importers.py", "tests/test_loop.py"]; [fn() for path in files for name, fn in runpy.run_path(path).items() if name.startswith("test_") and callable(fn)]'
```

## 11. Paper source

The single canonical manuscript is [`paper/main.tex`](paper/main.tex), with
references in [`paper/refs.bib`](paper/refs.bib), the editable workflow figure in
[`paper/abt_framework.svg`](paper/abt_framework.svg), and the compiled output at
[`paper/main.pdf`](paper/main.pdf). Build it from the repository root with:

```bash
tectonic --outdir paper paper/main.tex
```

The Prism-imported manuscript has been merged into this source and its duplicate
project folder/archive removed. Do not maintain a second manuscript copy.
