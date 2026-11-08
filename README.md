# readiness.index

Before an organization spends on AI, it should know where it actually stands. readiness.index scores readiness across six weighted dimensions (strategy, data, technology, talent, governance, operations), names the level, finds the gaps, and orders the work by how much each gap matters. Standard library only.

Looking for the guided version? The free [MAO Index](https://www.andmaverick.com/mao-index?utm_source=github&utm_medium=repo&utm_campaign=readiness.index) is the assessment I use with leadership teams. This repository is the scoring engine in code.

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

## Design

- **Weighted, and the weights are yours.** Data and governance carry the most weight by default because they are where programs most often stall. Pass your own weights and they are validated to sum to one.
- **Levels, not just a number.** Emerging, Developing, Scaling, Leading.
- **Roadmap by impact.** A gap is ranked by the points needed to close it times the dimension's weight, so the first item is the one that moves the overall score most.
- **Strict input.** Missing dimensions and ratings outside 1 to 5 raise errors.

## Tests

```
python -m unittest discover -s tests -t . -v
```

MIT licensed. Built by [AndMaverick LLC](https://www.andmaverick.com).

---

**Related reading:** [The Job Nobody Has Yet](https://blog.andmaverick.com/the-job-nobody-has-yet?utm_source=github&utm_medium=repo&utm_campaign=readiness.index)

**If this is your problem.** If you are deciding what to build, buy, and fund, I help leadership teams make that call with evidence. [Begin a conversation](https://calendly.com/andmaverick?utm_source=github&utm_medium=repo&utm_campaign=readiness.index).
