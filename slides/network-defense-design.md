# Network-level defenses beyond MTD: research and ABT implementation plan

## Scope and framing

This is a design proposal for ABT, not a claim that these controls are implemented
or that their effectiveness has been empirically demonstrated. NIST SP 800-215
surveys secure enterprise network architecture; SP 800-207 frames zero trust around
least-privilege, per-request access rather than implicit trust based on network
location; SP 800-41 Rev. 1 covers firewall policy. MITRE D3FEND gives a useful
defensive-technique vocabulary, while CISA's Protective DNS service is an
operational example of DNS response blocking, redirection/sinkholing, and alerting.
These sources describe architectures and techniques, not ABT's measured efficacy.
The candidate set includes both network- and host-based controls; MTD is retained as
a distinct action family and comparison condition.

MTD is not inherently dependent on SDN: endpoint firewall rules, DHCP/DNS,
virtual-machine or container networking, and NAT can implement address or port
changes. A coordinated SDN control plane is selected here as an experimental
assumption because it makes network-policy updates and virtual endpoint remapping
explicit; it is not a prerequisite for all MTD deployments.

The codebase now has an optional `SDNController` simulation state: virtual-IP
leases, a candidate address pool, blocked-flow rules, and a policy-update counter.
`shuffle_ip` remaps a virtual endpoint when the SDN state is enabled, while
`block_flow` records a controller rule; both continue to work against the abstract
flow model without an SDN controller. `evaluate()` and `MasterAgent.plan()` execute
actions on a cloned network and report risk, legitimate-flow availability,
performance, cost, SDN policy updates, and endpoint changes before a selected
`Plan` is applied to the in-memory state. No physical switch/controller is programmed.

## Candidate controls

| Control | Defensive value | ABT modeling approach | Priority / caveats |
|---|---|---|---|
| Least-privilege segmentation / ACLs | Limits lateral movement to explicitly required service connections. | Start from existing `Network.flows`; represent allow/deny policy actions over host/zone/service selectors. Recompute reachability and legitimate-flow availability after each simulated policy. | **P0, best first implementation.** `block_flow` is already a narrow primitive, but ABT does not yet model reusable zone policy, rule ordering, or policy semantics. |
| Ingress and egress filtering | Reduces exposed entry services and outbound C2 / exfiltration routes. | Add explicit external endpoints and directional flows; add policy selectors for source/destination, protocol, port, destination class/domain, and direction. Model exfiltration as an external-sink goal, rather than equating it with compromise of the data-host. | **P1.** Current graph treats a goal as reaching a host and lacks a data-transfer state; do not claim modeled exfiltration until that is fixed. |
| Protective DNS / DNS denylisting or allowlisting | Blocks or redirects queries for prohibited destinations and can produce alert telemetry. | Introduce DNS query events and resolver-policy state: client, qname/domain, record type, resolver, decision (allow/block/sinkhole), and optional threat label. Connect DNS decisions to modeled outbound endpoints. | **P1/P2.** A port-only flow graph cannot represent domain-based policy; avoid treating DNS blocking as equivalent to blocking all direct-IP access. |
| Network traffic analysis (NTA) / IDS | Provides visibility and detections; IDS itself observes, it does not necessarily block. | Add typed telemetry/detection events with sensor, flow, timestamp/round, confidence, rule, and outcome. Let the master update beliefs or propose response actions. Test detection and false-positive rates separately from prevention. | **P2.** Keep detection probability and prevention probability separate; do not silently reduce exploit probability for an IDS alert. |
| IPS / policy-triggered blocking | Prevents or interrupts selected traffic inline, with potential service impact. | Model as an explicit policy action that removes/denies a matched flow only after an alert or a planner decision; record the affected legitimate flows and action cost. | **P2.** Separate inline prevention from passive IDS; include false positives, latency, and rollback costs. |
| Graduated quarantine / network isolation | Contains a suspected compromised node while retaining essential management or recovery access. | Add host/zone state such as normal, restricted, quarantine; define allowed recovery/control-plane flows and a transition action. Evaluate isolation by weighted legitimate workflows and remaining attack paths. | **P2.** Current `isolate_host` deletes every incident flow; it is a coarse model and may disconnect response channels. |
| Identity/context-aware network access (ZTNA) | Enforces per-resource, least-privilege access using subject, device, and context rather than subnet location alone. | In a later extension, model identity/device attributes, policy decisions, and policy-enforcement points. A request is allowed only when the policy decision permits it. | **P3 / future.** Current hosts and flows have no users, device posture, sessions, or request-level identity. |
| Rate limiting / QoS controls | Can constrain scanning, abusive traffic, and resource exhaustion without fully blocking a service. | Add traffic demand/capacity and rate-limit state; measure throughput, latency, drops, and legitimate workload impact under load. | **P3 / future.** Not meaningful in the current binary-flow and weighted-availability model. |

### Host-based candidates

| Mode | Candidate | Feasibility and deployment concern |
|---|---|---|
| Proactive | Patch a known vulnerable service; disable a specifically identified unnecessary service. | Existing simulator actions; testbed implementation is feasible with allowlisted configuration-management tasks on disposable Linux guests. Generic CVE-to-package resolution and production patching are not selected. |
| Proactive | Host firewall baseline. | Technically deployable through OS policy (e.g., Linux firewall rules or centrally managed Windows Firewall), but adds a second policy-enforcement point and consistency/precedence problems with network ACLs. Defer from first experiment. |
| Proactive | Application allowlisting / process isolation. | Useful but requires OS- and workload-specific compatibility baselines, policies, and false-positive testing. Defer. |
| Reactive | Host quarantine after confirmed compromise. | Existing simulator can isolate a host; current all-flow removal is not safe enough to deploy. Select for simulation, refine to a recovery-aware policy before testbed enforcement. |
| Reactive | Credential rotation / revocation. | Requires identity provider, secret inventory, dependency mapping, and session invalidation; could disrupt services. Defer. |
| Both | MIR/EDR monitoring and response. | MIR event ingestion and response planning are modeled, but there is no real sensor or vendor agent integration. Use controlled/synthetic observations first; live sensor deployment is future work. |

## Selected initial portfolio: proactive and reactive

Selection criterion: feasible in the current graph model or with one small
extension, enforceable in a controlled benchmark range, measurable by the current
QoS/risk metrics, and reversible before any live application. This is a bounded
research prototype, not a claim of production readiness.

| Mode | Level | Selected capability | Why selected / simulator status | Testbed deployment path and guardrails |
|---|---|---|---|---|
| Proactive | Network | Least-privilege segmentation over known host/service flows. | Fits the existing `Network.flows` graph; can preserve declared `LegitFlow`s and compare attack-path cuts. Policy precedence / zone semantics are a small missing abstraction. | Start on Mininet/OVS with an OpenFlow controller on isolated Linux. Require policy diff, dry-run, read-back, approval, health check, and rollback. Docker endpoints are optional. |
| Reactive | Network | Block a specific attacker-relevant flow after a confirmed or injected detection. | `block_flow` is already simulated; the event/trigger path and policy log need to be explicit. | Reuse the same narrow OVS rule backend; preserve management/recovery and legitimate flows; never issue broad host/network blocks automatically. |
| Proactive | Host | Patch a known vulnerable service and disable an explicitly unused exposed service. | Both actions already mutate simulated service state and can reduce modeled attack paths. | In the initial testbed, use allowlisted Ansible tasks only on disposable Linux guests; verify package/service state and workflow health; no generic CVE-to-package automation or production patching. |
| Reactive | Host | Quarantine a confirmed compromised host. | `isolate_host` exists, so efficacy is measurable in simulation. It is currently too coarse because it removes every flow. | Before actuation, replace with a restricted host-firewall/EDR profile that retains controller, recovery, and forensic access; require approval and timed rollback. |
| Proactive baseline | Host + network | Retain current MTD actions: software diversity and IP/port shuffling. | Existing action catalogue and paper rationale; keep as a distinct comparator, not replaced by network ACLs. The optional SDN model records virtual-IP leases. | Treat as simulated baseline initially; real deployment is application/platform-specific. Compare MTD-only, selected non-MTD, and combined plans. |

The SDN control-plane model is an emulator, not a controller integration: it records
virtual-IP mappings and flow-block policy updates so action effects can be previewed
on cloned networks and measured before changing the in-memory model. The selected
subset separates \emph{what can be simulated now} from
\emph{what is deployable now}: the selected host changes and flow blocking have
model-level counterparts; the reusable segmentation policy and safe quarantine
semantics still need to be built, and no network controller or host actuator has
been integrated.
For an actual SDN experiment, the recommended first testbed is Mininet with
Open vSwitch (OVS) and an OpenFlow controller on an isolated Linux host or VM.
Mininet supplies a programmable virtual topology; OVS supplies the OpenFlow
datapath. Docker can host reproducible endpoint services, but Docker networking
alone is not an OpenFlow-controlled switch/controller and must not be reported as
an SDN experiment. A Docker-to-OVS attachment is an optional integration task, not
a requirement for the first topology. The current ABT controller remains a
simulator; neither testbed adapter is implemented. Docker Desktop on macOS is not
the target environment for kernel/OVS-level measurements.

### Candidates deferred from the initial subset

- **Egress filtering / exfiltration prevention:** valuable, but current goals do not
  require a data-bearing route to an external sink. Defer until that goal semantics
  and directional external endpoints exist.
- **Protective DNS:** requires resolver integration and domain/query state; direct-IP
  access and false blocking must also be modeled.
- **NTA / IDS sensors:** need real or benchmark sensor telemetry, confidence,
  false-positive rate, and alert delay. Keep evidence separate from IPS prevention.
- **ZTNA:** requires identity/device/session attributes and policy-enforcement
  points that are absent from the model.
- **Rate limiting / QoS shaping:** requires offered load, capacity, latency,
  throughput, and packet-drop metrics.
- **Application allowlisting, process isolation, credential rotation:** potentially
  useful host controls, but require OS/app compatibility policies or identity/secret
  infrastructure. They are not necessary to answer the first bounded planner
  evaluation.

### Implementation and deployment stages

1. **Policy contract (simulation only):** define ordered allow/deny policy rules,
   selectors, default action, stable IDs, and deterministic evaluation. Derive
   permitted flow reachability from that policy.
2. **Proactive planner run:** apply the baseline segmentation and selected host
   hardening before the first attack; the existing loop now supports an optional
   initial proactive plan for the actions in its current catalogue. Explicit
   segmentation candidate rules must be implemented before claiming proactive ACL
   evaluation. Test policy precedence, legitimate-flow preservation, risk reduction,
   and rollback snapshots.
3. **Reactive run:** inject a typed confirmed-compromise event, let ABT propose one
   narrow network block and/or host quarantine, then measure remaining attack paths,
   availability, and recovery connectivity.
4. **Linux testbed adapter:** first implement dry-run and read-back for an isolated
   Mininet/OVS topology and OpenFlow controller, with approval and rollback.
   Docker may provide endpoint containers but does not substitute for the
   programmable switch. nftables is an alternative for Linux firewall experiments;
   host changes can use narrowly scoped configuration management. Do not interpret
   atomicity as proof that a policy is correct.
5. **Out of scope:** Windows and heterogeneous fleets, production actuation,
   vendor-specific EDR integrations, automatic patching of arbitrary CVEs, and
   autonomous high-impact responses.

## Suggested interfaces (design only)

- `NetworkPolicy`: immutable selector, decision, priority, and stable rule ID.
- `Network.policy`: ordered policy state; the existing flow set remains derived or
  cached reachability, rather than an independent source of truth.
- `PolicyDecisionPoint.evaluate(request, context)`: pure allow/deny decision.
- `NetworkController.apply(policy_change)`: simulation backend first; future
  adapters (firewall/SDN/cloud security groups) must implement dry-run, read-back,
  approval, and rollback before live use.
- `NetworkEvent` / `Detection`: evidence and confidence, not a direct network-state
  mutation. The master decides whether to update beliefs or propose action.
- Evaluation tracks attack goal probability, legitimate workflow availability,
  flow/egress outcomes, detection false positives and delay, action cost, policy
  complexity, and (when modeled) latency/throughput.

## Limitations and validation requirements

- The current `Flow(src, dst, port)` abstraction has no protocol, direction, domain,
  identity, traffic volume, or enforcement-point concept.
- The proactive/reactive labels describe when the planner applies a control, not a
  permanent property of the technique. Segmentation and MTD can be triggered in
  either mode.
- Current `AttackGoal(kind="exfiltrate", host=...)` is treated by the attack graph as
  reaching a host; this is a proxy, not a data-exfiltration path model.
- `block_flow` and `isolate_host` are simulation mutations, not firewall/SDN
  integrations. No real network control should be enabled based on this prototype.
- CVSS/playbook probabilities and MIR/MTD reduction factors remain uncalibrated;
  evaluate uncertainty and correlated paths before interpreting risk numerically.
- Test these controls only on owned, isolated benchmarks/ranges. Keep production
  enforcement out of scope until policy correctness, rollback, and false-positive
  impact have been independently validated.

## References

1. NIST SP 800-215, *Guide to a Secure Enterprise Network Landscape* (2022):
   <https://doi.org/10.6028/NIST.SP.800-215>
2. NIST SP 800-207, *Zero Trust Architecture* (2020):
   <https://doi.org/10.6028/NIST.SP.800-207>
3. NIST SP 800-41 Rev. 1, *Guidelines on Firewalls and Firewall Policy* (2009):
   <https://doi.org/10.6028/NIST.SP.800-41r1>
4. CISA, *Zero Trust Maturity Model v2.0*:
   <https://www.cisa.gov/resources-tools/resources/zero-trust-maturity-model>
5. CISA, *Protective Domain Name System (DNS) Resolver*:
   <https://www.cisa.gov/resources-tools/services/protective-domain-name-system-dns-resolver>
6. MITRE D3FEND, *Network Isolation* (D3-NI):
   <https://d3fend.mitre.org/technique/d3f:NetworkIsolation/>
7. MITRE D3FEND, *Outbound Traffic Filtering* (D3-OTF):
   <https://d3fend.mitre.org/technique/d3f:OutboundTrafficFiltering/>
8. MITRE D3FEND, *DNS Denylisting* (D3-DNSDL):
   <https://d3fend.mitre.org/technique/d3f:DNSDenylisting/>
9. MITRE D3FEND, *Network Traffic Analysis* (D3-NTA):
   <https://d3fend.mitre.org/technique/d3f:NetworkTrafficAnalysis/>
10. NIST SP 800-53 Rev. 5, *Security and Privacy Controls for Information Systems
    and Organizations*: <https://doi.org/10.6028/NIST.SP.800-53r5>
11. CISA, *Federal Government Cybersecurity Incident and Vulnerability Response
    Playbooks*:
    <https://www.cisa.gov/resources-tools/resources/federal-government-cybersecurity-incident-and-vulnerability-response-playbooks>
12. Netfilter Project, *Atomic Rule Replacement*:
    <https://wiki.nftables.org/wiki-nftables/index.php/Atomic_rule_replacement>
13. Microsoft Learn, *Configure Firewall Rules With Group Policy*:
    <https://learn.microsoft.com/en-us/windows/security/operating-system-security/network-security/windows-firewall/configure>
