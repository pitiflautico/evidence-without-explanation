# Evidence without explanation: pilot studies on how a frontier agent uses (and fails to use) the computation it is offered

*Technical report, October 2026. Independent research. Draft. Revised on 27 October 2026: see §0.*

## 0. Corrections (27 October 2026)
On 27 October we re-checked every figure in this report against the raw logs. The check was read-only, with no new
runs. The table keeps the previous wording for traceability.

In the last column:
- **reporting:** an error in how we wrote it up;
- **omission:** a qualifier or result we left out;
- **instrument:** our tooling distorted the measurement.

None of these corrections changes what is attributed to the agent's own behaviour, except where the table says so.

| # | Where | Previously stated | What the re-check found | Corrected statement | Type |
|---|---|---|---|---|---|
| 1 | §3.2 | "+0.62 (95 % CI +0.43 to +0.81)"; "−0.48 (CI −0.67 to −0.24)" | Both are paired bootstrap intervals at **90 %**. The reading was fixed before running, but the lab was run and closed as exploratory. | 90 % intervals, exploratory comparison. | Reporting |
| 2 | §3.1 | "Sub-contexts: 0 of 31 episodes" | Correct for the two pilots reported here (21 + 10). Two runs not reported here also offered sub-contexts: 0 of 54. | 0 of 31 in these pilots; 0 of 85 across all our runs that offered them. | Omission |
| 3 | §3.1, README | Code store: "0 of 8 functional uses"; offered capabilities "almost never used" | True for importing or executing stored code. We left out that in the transplant arm of "Lab B with feedback" the agent copied or adapted stored code in 5 of 8 episodes. It solved 3 of those 5; the arm without inheritance solved all 5. | Stored code is not imported, but it is reused by copying, with no demonstrated benefit. | Omission |
| 4 | §3.3 | "visible (43 of 43) and identifiable (40 of 43)" | The counts cover only failures whose cause the auditor could isolate by removing one mechanism; 83 failing scenarios had no single isolable cause. "Identifiable" is a provisional verdict (the optimiser may miss a better alternative), tested against the generator's catalogue of mechanisms, which the agent does not know. | Same figures with these qualifiers. They bound from above what the agent could have identified. | Omission |
| 5 | §3.5 | "At equal budget, though, it spends the budget on reasoning and does not turn into results: the three episodes that proposed it never delivered." | One of those three (the borderline case, axe-10) had a controller already validated 6/6 when our budget mechanism stopped the episode at 0.41 of 0.60 USD. All 7 out-of-budget stops come from a worst-case cost reservation the agent could not see. | Because of our budget mechanism, the score comparison does not show whether high effort turns into results. **Inconclusive.** The increase in the right explanation family stands. | Instrument |
| 6 | §5 | Not reported | Two instrument issues affect these pilots. (a) Budget stops: 3 of 40 pilot episodes and 7 of 10 high-effort episodes. (b) The sandboxed Python tool starts a fresh process per call and its description did not say so; at least one `NameError` appears in 28 of 40 pilot conversations and 8 of 10 high-effort conversations. | Added to §5. | Instrument |
| 7 | §4 | "Capabilities offered as options do not fix this, because using them requires exactly the recognition that is missing." | In these pilots the minimal procedure was often good enough. Not using an option is therefore not separated from having no incentive to use it. | Kept as our interpretation, now labelled as such. | Reporting |

## Abstract
We ran a series of small, pre-registered pilots with a frontier model (Claude Opus 5.5) acting as an agent on
simulated control problems with hidden mechanisms. An offline auditor replays every episode deterministically and
attributes failures to their causes.

Four results recur:
1. **The evidence the agent needs is usually in its own data.** It was visible in 43 of 43 failure causes and
   identifiable in 40 of 43.
2. **When the agent fails, it is mostly because it does not generate the right family of explanations, not because
   it did not explore.** For hysteresis: 18 interpretation failures, 0 exploration failures, out of 36 episodes.
3. **Capabilities that are offered (code memory, sub-contexts, a validated hypothesis-testing module) are almost
   never used.** Stored code is not imported, but it is sometimes copied (§0, item 3).
4. **Structure imposed from outside (mechanical coverage, feedback from validations) does change outcomes.**

We report the null results with the same weight. We discuss what this implies for building agents that notice what
they are not considering.

## 1. Testbed
- **Machines:** 2 actuators and 2 sensor channels. Hidden mechanisms drawn from: delay, accumulation, saturation,
  discrete regime switch, hysteresis, sensor aliasing (held readings) and drift. Read noise σ = 0.02.
- **What the agent sees:** only actuators, channels, target, tolerance and budgets. The agent is never shown the
  catalogue of mechanisms.
- **Tools:** act on the machine (400 steps), read, run Python in a sandbox (60 s per run), validate a controller
  on 6 validation scenarios (up to 3 times), deliver.
- **Scoring:** the delivered controller is scored on held-out scenarios. A problem is solved at ≥ 0.9.
- **Difficulty:** problems are accepted only if a reference controller with full knowledge solves them (≥ 0.9) and
  two conventional methods do not (the "hard" stratum).

The auditor, never seen by the agent:
- replays validations with each mechanism removed, to attribute failures;
- fits alternative explanations to the observed trajectories, to test identifiability;
- replays the agent's exploration on the true machine, to count regime changes the agent actually provoked.

## 2. Pilots
| Pilot | Arms | n | Spend |
|---|---|---|---|
| Lab A (rule problems) | D, COB, DET, DET_X, AUTO | 21 problems × 5 | 6.40 USD |
| Lab B (machines) | fixed vs. code store; transplant | 32 episodes | 2.21 USD |
| Lab B with feedback | 4 build arms × 8; 5 transplant arms × 8 | 72 episodes | 9.38 USD |
| A / A_HINT / A+ / X | plain; hint to contrast hypotheses; hint + contrast module; sub-contexts | 10 problems × 4 | 8.64 USD |

All banks, code and environment versions are frozen with hashes before each run. Changes are declared before
running. Results are written once and kept read-only.

## 3. Results
### 3.1 Offered capabilities are not used
| Capability | Use |
|---|---|
| Code store across problems | 0 of 8 functional uses (import or execution) |
| Stored code in the transplant arm of Lab B with feedback | not imported; copied or adapted in 5 of 8 episodes (3 of those 5 solved, vs. 5 of 5 without inheritance) |
| Sub-contexts | 0 of 31 episodes in these pilots (0 of 85 across all our runs that offered them) |
| Hypothesis-contrast module (validated: 41 of 43 agreement with the auditor) | 1 of 10 episodes |

### 3.2 Imposed structure works
| Intervention | Effect |
|---|---|
| Mechanical coverage | +0.62 success (90 % CI +0.43 to +0.81; n = 21, paired; exploratory) |
| Model-based needs detector instead of coverage | −0.48 (90 % CI −0.67 to −0.24) |
| Feedback from validations | 6 of 8 vs. 3 of 8 (single sequence) |

The coverage signal matches documents using the generator's own wording, and its recall was measured on the
calibration bank. It shows that an imposed check helps when its designer knows where the decisive information is. It
does not show that the agent could build such a check.

### 3.3 Evidence without explanation
- The cause of each validation failure was visible in that validation's data (43 of 43) and identifiable (40 of 43):
  alternative explanations fit worse than the true one by more than max(0.04, 1.5×) RMS. Three qualifiers (§0,
  item 4):
  - the counts cover only failures with a single isolable cause; 83 failing scenarios had none;
  - "identifiable" is provisional;
  - identifiability is tested against the generator's catalogue, unknown to the agent.

  So 40 of 43 is an upper bound.
- Hysteresis, 36 episodes. Classification fixed before computing:
  | Class | Episodes |
  |---|---|
  | Solved | 6 |
  | Hysteresis irrelevant | 10 |
  | Exploration failure | 0 |
  | Interpretation failure | 18 |
  | Action failure | 2 |
  - In every episode where hysteresis mattered, the agent's own data contained regime jumps of 0.8–1.5 (noise 0.02).
  - Hysteresis was identifiable in 29 of 29 validations where it caused failure.
  - It was proposed in 2 of 36 episodes. By contrast, saturation and linear memory were proposed in half or more of
    the episodes where they were present.
- A generic operation without privileged information (regime reset + step identification + integral control)
  solves 23 of 40 new problems with regime mechanisms, against 6 of 40 without the reset. On the pilot bank, though,
  it solves only 1 of 9. The evidence was interpretable, but a cheap fix rarely existed.

### 3.4 Null result: architectures
In the A / A_HINT / A+ / X pilot (pre-registered), no arm differs from the plain agent beyond noise:
| Arm | Solved |
|---|---|
| A | 1 of 10 |
| A_HINT | 2 of 10 |
| A+ | 1 of 10 |
| X | 2 of 10 |

Blind auditing of explanation families (fixed codebook F0–F7) shows no clear difference either.

### 3.5 Effort control
Plain agent, same 10 problems, high reasoning effort, same dollar cap per episode:
| | Low effort | High effort |
|---|---|---|
| Solved | 1 of 10 | 1 of 10 |
| Mean score | 0.44 | 0.18 |
| No delivery | 1 | 8 (7 out of budget) |
| Hysteresis-type explanation proposed (9 problems) | 0 | 2 clear + 1 borderline |

- Higher effort makes the right family appear somewhat more often.
- None of the three episodes that proposed it delivered. One of them (axe-10, the borderline case) already had a
  controller validated 6/6 when our budget mechanism stopped it at 0.41 of 0.60 USD. All 7 out-of-budget stops come
  from a worst-case cost reservation that the agent could not see.
- The score comparison is therefore confounded by our instrument. Whether high effort turns into results at equal
  budget is inconclusive (corrected on 27 Oct; §0, item 5).
- 4 of 158 responses hit the output-token limit, against our own pre-registered stopping rule. We report it.
- High effort with a larger budget is untested.

### 3.6 Exploratory observations
- **External attribution:** unexplained jumps were attributed 8 times to a drift or disturbance that the bank does
  not contain.
- **Variance across attempts:** mean 0.475 per attempt; 0.675 when choosing among 4 attempts by the agent's last
  validation (correlation 0.85). Post hoc, budget not equalised.

## 4. Discussion
The bottleneck we observe is not capability in the narrow sense. The agent writes working controllers for the mechanisms it does
consider. We have not yet tested whether naming the missing mechanism is enough. Nor is it information: the data
were there. The bottleneck is **recognising which
operation the problem needs**:
- proposing a new family of explanation when the current one keeps failing;
- choosing to test hypotheses rather than tune parameters;
- surfacing an anomaly rather than absorbing it as noise or an external disturbance.

Our interpretation is that capabilities offered as options do not fix this, because using them requires exactly the
recognition that is missing. We have not separated this from lack of incentive: in these pilots the minimal procedure
was often good enough. Structure imposed from outside does help, at the cost of rigidity, when its designer knows
where the decisive information is.

The open question is whether there is a general mechanism, neither imposed nor optional, that makes an agent notice
what it is not considering. Event-triggered operations are one candidate.

## 5. Limitations
- One model and one provider. Low reasoning effort, except for one control that is confounded by the budget.
- Small n: 8 to 21 problems per comparison. Most comparisons are descriptive.
- Simulated machines: generalisation to open-ended tasks is untested.
- Explanation families were coded by one auditor per conversation, with partial blinding.
- The generic capability in §3.3 was designed by us knowing the class of machines. It bounds what a generic
  operation can do, not what the agent could have invented.
- **Instrument issues** (ours, not the agent's; added on 27 Oct):
  - **Budget stops.** A worst-case cost reservation the agent cannot see stops episodes early: 3 of 40 pilot
    episodes and 7 of 10 high-effort episodes.
  - **Stateless Python tool.** It starts a fresh process per call and its description did not say so: at least one
    `NameError` in 28 of 40 pilot conversations and 8 of 10 high-effort ones.
  - **Empty reasoning.** At low effort the reasoning blocks are empty, so "not proposed" is inferred from code and
    text only.
