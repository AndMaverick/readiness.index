# readiness.index

Before an organization spends on AI, it should know where it actually stands. readiness.index scores readiness across six weighted dimensions (strategy, data, technology, talent, governance, operations), names the level, finds the gaps, and orders the work by how much each gap matters. Standard library only.

Looking for the guided version? The free [MAO Index](https://www.andmaverick.com/mao-index?utm_source=github&utm_medium=repo&utm_campaign=readiness.index) is the assessment I use with leadership teams. This repository is the scoring engine in code.

Version 0.2 treats a readiness score as evidence that has to survive review, not a number from a form. It scores real respondent data against a documented instrument (24 questions, each with what a 1, a 3 and a 5 look like), and then answers the questions a skeptical board member asks:

- How far should we trust this? Bootstrap intervals, the probability the organization is really at each level, and rater agreement.
- Do people see the same company? Gaps between roles (executives versus practitioners), and the specific questions where raters are three or more points apart.
- Is the high score earned? Items rated 4 or higher with no evidence on file are listed.
- Is one weak area hiding behind a good average? A bottleneck rule caps the level one step above the weakest dimension.
- What do we do first? The exact best order for closing gaps when some work must precede other work.
- Did anything really change since last time? Change with an interval, dimension by dimension, and a verdict.
- Does it clear the bar we set in advance? Gates make the command exit 1 when it does not, so a review checklist or a pipeline can enforce it.

## Use

```python
from readiness_index import gaps, roadmap, score

answers = {            # ratings from 1 to 5, any number per dimension
    "strategy": [4, 4], "data": [2, 3], "technology": [4, 3],
    "talent": [3, 3], "governance": [1, 2], "operations": [3, 4],
}

result = score(answers)
result["overall"], result["level"]    # (47.5, 'Developing')
gaps(result)                          # [('governance', 47.5), ('data', 22.5), ('talent', 10.0)]
roadmap(result)                       # the same gaps ordered by weighted impact
```

That is the 0.1 interface and it behaves exactly as before. The 0.2 workflow starts from a file of respondents:

```
python -m readiness_index assess assessment.json              # report; exit 0 pass, 1 a gate failed, 2 unusable input
python -m readiness_index assess assessment.json --json       # the same, machine readable
python -m readiness_index compare before.json after.json      # change with intervals
python -m readiness_index instrument                          # the 24 questions and their anchors
python -m readiness_index fingerprint assessment.json         # SHA-256 of input + version + method
```

```python
from readiness_index import analyze, loads

result = analyze(loads(open("assessment.json").read()))
result["level"], result["overall_interval"], result["plan"]["order"]
```

## The assessment file

```json
{
  "name": "Acme Logistics, Q4 2026",
  "respondents": {
    "cfo":  {"role": "executive",    "ratings": {"strategy.1": 4, "data.2": 3, "governance.3": null}},
    "lead": {"role": "practitioner", "ratings": {"strategy.1": 3, "data.2": 2}, "weight": 2}
  },
  "evidence": {"strategy.1": "Board paper 2026-03, approved portfolio with named owners"},
  "targets": {"default": 60, "governance": 70},
  "effort_per_point": {"default": 1.0, "data": 1.6},
  "prerequisites": {"operations": ["data", "governance"]},
  "simulation": {"resamples": 2000, "seed": 5},
  "gates": {"min_level": "Scaling", "min_dimension": 50, "max_perception_gap": 20, "max_unsupported_high": 0,
            "target_level": "Scaling", "min_prob_level": 0.9}
}
```

Loading is strict: an unknown key, a repeated key, a rating outside 1 to 5, an unknown question id or a NaN is an error, never a silent default. A rating of `null` means "I do not know", which is different from a low rating and is tracked as coverage. Weights default to the 0.1 dimension weights (data and governance 20 percent, the rest 15) and may be replaced with a custom instrument. Targets are scores from 0 to 100 or level names. Gates are `min_overall`, `min_level`, `min_dimension`, `min_coverage`, `min_respondents`, `max_contested_items`, `max_perception_gap`, `max_unsupported_high`, `min_agreement`, and `target_level` with `min_prob_level`.

Two scenarios ship in `examples/` (synthetic organizations; `examples/generate_examples.py` regenerates them). `acme_assessment.json` clears every gate. `northgate_assessment.json` does not, and this is what it prints:

```
Northgate Retail, Q4 2026 (synthetic example)   (readiness.index 0.2.0, fingerprint c90bb4c9d86bec1f)

Overall 47.0 out of 100 (95% interval 33.7 to 61.2), from 9 respondents
Level: Developing
Resampled panels land on: Emerging 15%, Developing 82%, Scaling 3%

Dimensions
  dimension     score  95% interval   target weight
  governance     25.6  14.0 to 37.6       60    20%
  operations     36.0  21.1 to 51.2       60    15%
  data           45.1  31.4 to 59.5       60    20%
  talent         55.3  37.2 to 71.6       60    15%
  technology     59.7  45.5 to 75.2       60    15%
  strategy       68.1  53.2 to 83.6       60    15%

Do people agree?
  raters differ by 1.06 rating points on an average item (standard deviation); 16 items are contested (3+ points apart)
  Krippendorff alpha, how well raters track differences between items: 0.193, unreliable
  answers given: 94%
  contested: data.4 rated from 1 to 5
  contested: strategy.3 rated from 1 to 5
  contested: talent.1 rated from 1 to 5
  technology: executive rates it 46.9 points above practitioner
  operations: executive rates it 45.8 points above practitioner
  strategy: executive rates it 44.8 points above risk

Rated 4 or higher with no evidence on file (1): strategy.2

Weakest items
  governance.3   1.88 out of 5
  governance.4   2.00 out of 5
  governance.1   2.11 out of 5
  governance.2   2.11 out of 5
  data.2         2.22 out of 5

Roadmap (exact best order, respecting prerequisites)
  1. governance   +34.4 points, effort 0.0 to 31.0, overall 53.9, level Developing
  2. talent       +4.7 points, effort 31.0 to 36.1, overall 54.6, level Developing
  3. data         +14.9 points, effort 36.1 to 59.9, overall 57.6, level Developing
  4. operations   +24.0 points, effort 59.9 to 88.7, overall 61.2, level Scaling
  5. technology   +0.3 points, effort 88.7 to 89.0, overall 61.2, level Scaling

Gates
  PASS  min_level: level Developing, required Developing
  FAIL  min_dimension: weakest dimension governance at 25.6, required 40
  FAIL  max_contested_items: 16 items where raters are 3 or more points apart, allowed 2
  FAIL  max_perception_gap: widest gap 46.9 points on technology (executive vs practitioner), allowed 20
  FAIL  min_coverage: 93.5% of answers given, required 95.0%
  FAIL  max_unsupported_high: 1 item rated 4 or higher with no evidence on file, allowed 0
  PASS  min_respondents: 9 respondents, required 6
  FAIL  min_prob_level: 85.1% of resampled panels reach Developing, required 90.0%

RESULT: FAIL
```

The average looks like a company that is Developing. The review shows executives rating technology 47 points above the people who run it, a governance score of 26 that is the weakest by a distance, 16 questions where raters are three or more points apart, and a panel too small to rule out Emerging. The exact roadmap closes governance first and leaves operations until data and governance are done, because operations depends on both.

Change over time, from `examples/acme_before.json` to `examples/acme_assessment.json`:

```
Acme Logistics, Q1 2026 (synthetic example)  ->  Acme Logistics, Q4 2026 (synthetic example)

                before   after  change  95% interval for the change  verdict
  overall         47.3    72.4   +25.1  +21.8 to +28.2               reliable gain
  data            45.3    75.0   +29.7  +21.4 to +37.5               reliable gain
  governance      28.9    77.1   +48.2  +39.9 to +56.9               reliable gain
  operations      47.7    68.1   +20.4  +15.7 to +25.0               reliable gain
  strategy        59.4    75.7   +16.3  +8.7 to +24.8                reliable gain
  talent          53.9    61.8    +7.9  -0.9 to +16.2                within noise
  technology      55.5    74.3   +18.8  +12.6 to +25.2               reliable gain
```

Talent moved by eight points, but the interval crosses zero, so this panel does not support saying it improved.

## Design

- **Exact scoring.** Dimension and overall scores are computed in rational arithmetic, so a result sitting exactly on 60.0 is Scaling, not Developing because of floating point.
- **Bottleneck rule.** A weighted average lets strength in one area pay for failure in another. The reported level is the level the average earns, capped at one step above the weakest dimension, and the report says which dimension held it down.
- **Roadmap by exact optimization.** Gaps are closed one after another. Finishing valuable work early is worth more than finishing it late, so the order minimizes the sum of benefit times completion time, subject to prerequisites. Without prerequisites that is the benefit per effort rule. With them that rule can be wrong, and the problem is hard in general, but a plan has a handful of gaps, so `readiness_index/planner.py` finds the exact optimum by dynamic programming over subsets (up to 16 gaps).
- **Uncertainty from the panel.** Respondents are resampled with replacement, seeded, with the small panel correction that makes intervals honest for panels of ten or fewer.
- **Pinned.** Every result carries a SHA-256 fingerprint of the input, the library version and the method. Two people running the same file get the same fingerprint and the same numbers.

## Evidence

The scoring, the agreement statistic and the sequencer are tested against implementations that share no code with them (`tests/oracles.py`): a straight from the definition rational recomputation, Krippendorff's coincidence matrix method, and brute force over every permutation. The agreement code also reproduces the published value (alpha 0.849) from Krippendorff's worked example. `python examples/evaluate.py` reruns everything from fixed seeds:

```
Krippendorff alpha vs the coincidence-matrix method: 296 random rater designs, largest gap 5.6e-16
exact scores vs a from-the-definition recomputation (rational arithmetic): 250 panels with gaps and weights, differences 0
roadmap order vs brute force over every permutation: 400 random plans, differences 0; the benefit-per-effort rule was beaten in 59, by 8.3% of its cost on average
95% bootstrap interval, coverage of the true score over 120 simulated panels: 88% with 8 respondents, 95% with 24
reliable-change flag over 100 simulated before/after pairs of 9 respondents: 11% flagged when nothing changed, 100% flagged for a true 10-point gain
2000 bootstrap resamples of a 12-respondent, 24-item assessment: 1.1 s
```

The suite has 75+ tests: oracles, invariances (respondent order, duplicated respondents, uniform shifts), boundary exactness, strict input rejection, gate behavior, exit codes, and identical output under different `PYTHONHASHSEED` values.

## Honest limits

- A score is only as good as the ratings. The instrument fixes what a 1, 3 and 5 mean and the evidence audit shows where a high rating has nothing behind it, but a panel that is wrong together will be wrong with a narrow interval.
- Intervals describe panel sampling, not bias. Even with the small panel correction they are somewhat optimistic below about a dozen respondents: in simulation the 95% interval covered the true score 88 percent of the time with 8 respondents and 95 percent with 24.
- "Reliable change" means the interval for the change excludes zero. With 9 respondents per wave it flagged 11 percent of no change pairs, so read it as "probably real", and collect more respondents before acting on a borderline result.
- Krippendorff's alpha rewards raters for tracking differences between questions. In a company that is uniformly mid level it is low even when the panel agrees closely, which is why the report also gives the average disagreement in rating points and the list of contested questions.
- The level bands (40, 60 and 80) and the one step bottleneck are conventions, stated in the output. The roadmap is only as good as the effort per point and the prerequisites you supply; the defaults treat every point as equal effort with no prerequisites.
- Exact results are identical everywhere. Bootstrap results are reproducible for a given seed on a given Python version; a different Python's random generator may differ in the last digits.

## Tests

```
python -m unittest discover -s tests -t . -v
```

MIT licensed. Built by [AndMaverick LLC](https://www.andmaverick.com).

---

**If this is your problem.** If you are deciding what to build, buy, and fund, I help leadership teams make that call with evidence. [Begin a conversation](https://calendly.com/andmaverick?utm_source=github&utm_medium=repo&utm_campaign=readiness.index).
