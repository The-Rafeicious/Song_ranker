# Optional selector QA

The live app imports only the standard-library `selection.py` and the read-only
`selection_data.py` adapter. This folder is a separate offline experiment kit.
It never imports Flask or opens the app database. NumPy is needed only here. The full benchmark was run with Python 3.12 and
NumPy 2.3.5; the live app and standard-library selector tests retain their existing
Python requirements.

From the app folder, in a QA environment:

```sh
python -m pip install -r tools/selection_lab/requirements.txt
python tools/selection_lab/run_deployed.py
```

The command writes `tools/selection_lab/results.json`. Keep a copy before another
run if comparing reports. `reference.py` contains the original tested prototype;
`legacy_selection.py` is the old selector used as its baseline. The input is the
anonymous 507-song feature snapshot from the supplied V3.4.13 database, not a
restorable database or a list of music titles. Its source checksum is recorded.

The deployed runner first checks 500 seeded prototype/production draws with
changing counts and recency. It then runs the original eight-seed growth,
imbalance, live K32, mode exposure, tournament entry, Shelf feasibility and
Guesser gap experiments through the deployed helpers. In total, 1,205 checks,
354,400 questions and 3,200 bracket draws passed in the step 5 run. Its statistics
matched the original report within 1e-10. Separate endpoint tests exercise actual
eligibility, saved counts, pending rounds and frozen answers.

Step 6 enables progressive Guesser targets from the pure `challenge_rules.py`.
For a separate standard-library check, run:

```sh
python tools/selection_lab/run_challenges.py
```

This writes `challenge_results.json` beside the script. It checks 19,200 draws
across eight seeds and streaks 0/10/25/50/100/250, plus 100 rating scale/offset
checks. Gap quantiles fall with the target while exposure and randomness remain.
The frozen 507-song fixture's median raw gaps were 29.83 at streak 0 and 3.81 at
streak 50; those are observations, not fixed selection cutoffs. The surviving
284 Trivia results backtest to 220 under classic rules and 46 under progressive
rules. This offline comparison never rewrites results or the saved 221 record.

Simulations test balance and feasibility; they do not establish preference
accuracy or replace the final desktop/phone/audio play-test. Standard-library
unit/endpoint regressions are in `tests/test_selection.py`,
`tests/test_selection_endpoints.py` and `tests/test_challenges.py`.
