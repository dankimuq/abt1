# ABT DSN 2027 presentation

`ABT_DSN_2027.pptx` is the editable 16:9 English research-in-progress deck.
Its content is generated from `build_deck.py`; edit that source and rebuild rather
than editing the generated PowerPoint directly, or subsequent builds will overwrite
manual edits.

`network-defense-design.md` records the source-grounded non-MTD control survey and
the selected proactive/reactive host and network control subset, feasibility,
deployment boundaries, deferred options, and evaluation requirements. MTD controls
are retained as a separate baseline. The deck assumes an SDN control-plane emulator
for repeatable network policy and endpoint-mapping simulations; MTD remains
deployable without SDN through alternative mechanisms.
The planned SDN validation uses Mininet/Open vSwitch on isolated Linux; Docker is
optional for hosting endpoint services and is not treated as an OpenFlow datapath
by itself.

## Rebuild

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r slides/requirements.txt
.venv/bin/python slides/build_deck.py
```

The generated presentation stays in this directory. The deck is organized into:

1. Title
2. Introduction and research questions
3. Related work
4. Proposed research, model, proactive/reactive host and network defenses, selected
   implementation/deployment subset, planning, and feedback loop
5. Experiments and verification status
6. Limitations, roadmap, and conclusion
7. Selected references

## Keeping the deck current

- Keep implementation claims consistent with `PROGRESS.md` and the code.
- Update the experiment-status slide only when reproducible results exist; label
  simulator demonstrations separately from benchmark or real-range evidence.
- Recheck citations, author details, submission status, and DSN 2027 requirements
  before external presentation.
- Network defense actions listed as planned/future work are not implemented merely
  because they appear in this proposal deck.
