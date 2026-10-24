# Evidence without explanation

A testbed and pilot data on how a frontier LLM agent uses, and fails to use, the computation it is offered.

The agent controls simulated machines with hidden mechanisms:
- delay;
- accumulation;
- saturation;
- regime switch;
- hysteresis;
- sensor aliasing;
- drift.

An offline auditor that the agent never sees replays every episode deterministically and does three things:
- attributes each failure to its cause;
- tests whether that cause was identifiable from the agent's own data;
- classifies the explanations the agent proposed.

**Main finding so far:** when the agent fails, the evidence it needed was usually already in its data. In the
hysteresis audit there were 18 interpretation failures and 0 exploration failures out of 36 episodes. Capabilities
offered as options (sub-contexts, a validated hypothesis-testing module, a code store) are almost never used. See
[`REPORT.md`](REPORT.md) for all results, including the null ones.

## Layout
| Path | Contents |
|---|---|
| `generadores/maquinas.py` | Machine simulator and problem generator (deterministic by seed) |
| `base/maquinas_entorno.py` | Agent world: actions, sandboxed Python (`sandbox-exec`, macOS), validation, delivery |
| `base/maquinas_hipotesis.py` | The four arms: A, A_PISTA (hint), A_MAS (hint + `contraste` module), X (sub-contexts) |
| `base/taller/contraste.py` | Hypothesis-contrast module offered to A_MAS. It fits hypotheses the agent writes and never proposes any |
| `ejecutor/` | Agent loop, budgets, resumable runner (`hipotesis_correr.py`) |
| `medir/` | Auditor: failure attribution (`anclaje`), identifiability, functional signatures, blind export, hysteresis audit |
| `bancos/maquinas/` | Frozen problem banks and file hashes (`congelado.json`) |
| `resultados/hipotesis-piloto/` | 40 episodes: log, full conversations, workshops, blind audit and classifications |
| `resultados/descubrimiento-fase0/` | Earlier audits: anchoring, evidence, identifiability, contrast module vs. auditor |

Code, comments and logs are in Spanish; the report is in English.

## Running
macOS only: the sandbox uses `sandbox-exec`.
```
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q tests                    # no API calls
.venv/bin/python -m medir.histeresis_piloto episodios resultados/hipotesis-piloto \
    resultados/hipotesis-piloto/auditoria/ciego resultados/hipotesis-piloto/auditoria/clave_ciego.json
```
Re-running the agent needs `ANTHROPIC_API_KEY` and costs money (about 0.2–0.6 USD per episode).

## Method
- Banks, code and environment are frozen with hashes before every run, and changes are declared before running.
- Decision rules and classifications are written down before computing.
- Comparisons are paired by problem.
- Results are written once and kept read-only.
- Negative results are reported with the same weight as positive ones.

## Status
Pilot-scale (n = 10–36 per comparison), one model (Claude Opus 5.5). Everything here is preliminary.
