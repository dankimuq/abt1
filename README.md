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

## 3. Mapping asset → defence (kill-chain, per the MTD-in-depth paper)

Each `Action.phase` is tagged with a kill-chain phase (recon, weaponize, deliver, exploit, install, c2, objective). Current tags: IP shuffle→recon, diversity→weaponize, patch/MIR/disable→exploit, flow blocking/isolation→c2. **Please verify and refine this table against the paper's actual technique taxonomy**, then extend the catalogue (e.g., credential rotation, decoys, data encryption for the objective phase), and let the master prefer plans covering multiple phases for crown-jewel assets.

## 4. Red-team integration

`abt/red.py` defines `RedTeamAdapter`. The shipped adapters (Incalmo, APT-Agent, AutoHacker) are Monte-Carlo stand-ins with different persistence levels, so the pipeline is testable without a live range. For the paper, replace them with real runs in a testbed (e.g., Incalmo's range environment): translate each tool's goal into `AttackGoal` and its observed behaviour into MIR events.

## 5. Suggested paper structure

1. Introduction – LLM-driven attackers (Incalmo, APT-Agent) outpace manual defence.
2. Background – HARM (HARMer), security models/metrics (Enoch 2021), MTD-in-depth.
3. ABT framework – the 6 components above; threat model; goal-aware attack graph.
4. Defence planning – utility formulation, constraints, algorithms.
5. Evaluation – RQ1: reduction in goal success vs. each attacker; RQ2: legit-user availability/performance cost; RQ3: planner optimality/scalability (hosts 10–1000); RQ4: reaction time to MIR alerts; ablations (host-only vs. network-only vs. both; with/without simulation).
6. Discussion – model fidelity, adaptive attackers, false positives, safety of autonomous response (human approval gate).

## 6. Known limitations / next steps

- Probabilities (MIR block 0.6, diversity 0.7, shuffle 0.6) are placeholders; calibrate with testbed data.
- Paths assume independence (noisy-OR over paths overestimates correlated paths).
- MIR is simulated; a real agent needs sensors (process, network, auth logs) and a signed command channel to the master.
- Network controller is a model mutation; add backends (iptables/SDN/cloud security groups).
- Attacker adaptation (re-planning after defence changes) is only approximated via `persistence`.

## 7. Run

```
python3 examples/run_demo.py
python3 -c "import tests.test_abt as t; [getattr(t,n)() for n in dir(t) if n.startswith('test_')]"
```
