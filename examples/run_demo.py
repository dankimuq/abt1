"""Run ABT on the example network: plan, validate against simulated red-team tools, react to an alert."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from abt import MasterAgent
from abt.red import APTAgentAdapter, IncalmoAdapter, success_rate
from examples.enterprise import build


def main():
    net, goals = build()
    master = MasterAgent(net, goals)
    print("Top attack paths:")
    for g, ps in master.attack_surface().items():
        for p in ps[:3]:
            print(f"  goal={g:3s} {' -> '.join(p.hosts)}  ASP={p.asp:.3f}")

    attackers = [IncalmoAdapter(goals), APTAgentAdapter(goals)]
    base = {a.name: success_rate(net, a) for a in attackers}

    plan = master.plan()
    print("\nRecommended plan:")
    for a in plan.actions:
        print(f"  [{a.level:7s}|{a.phase:8s}] {a.name} (cost {a.cost})")
    b, a_ = plan.before, plan.after
    print(f"\nrisk {b.risk:.3f}->{a_.risk:.3f} | availability {b.availability:.2f}->{a_.availability:.2f} "
          f"| performance {b.performance:.2f}->{a_.performance:.2f} | cost {a_.cost} | utility {b.utility:.3f}->{a_.utility:.3f}")

    after_net = net.clone()
    for act in plan.actions:
        act.apply(after_net)
    print("\nSimulated red-team success rate (before -> after):")
    for at in attackers:
        print(f"  {at.name:10s} {base[at.name]:.3f} -> {success_rate(after_net, at):.3f}")

    # Runtime loop: MIR on web reports compromise -> replan from that foothold
    master.execute(plan)
    master.ingest({"type": "compromise", "host": "app"})
    p2 = master.plan()
    print(f"\nAfter MIR alert (app compromised): replanned {len(p2.actions)} extra actions, risk {p2.before.risk:.3f}->{p2.after.risk:.3f}")
    for a in p2.actions:
        print("  ", a.name)


if __name__ == "__main__":
    main()
