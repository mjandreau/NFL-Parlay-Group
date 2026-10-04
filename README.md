# Pine Meadow Brolay Tracker

Weekly NFL parlay report for Matt, Dan, Dad and Nick. $10 each, one leg each, every Sunday.

The season lives in one JSON file. One script turns it into `Brolay_<season>.pdf`:
the group's record and bankroll, a leaderboard, who beats their odds, weekly awards,
and a page for every week.

Latest report: https://mjandreau.github.io/NFL-Parlay-Group/

## Setup

Python 3 (run here on 3.12 and 3.13).

```
pip install reportlab matplotlib pytest
```

## Weekly routine

1. Sunday morning: add the week to `brolay_data.json` with `"result": null` and
   `"score": null` on every leg.
2. After the games: set each leg's result to `"hit"`, `"miss"` or `"push"` and fill in
   the score.
3. Run `python build_report.py`. The PDF is rewritten in place.
4. Commit the PDF and push to `main`. The site updates a minute or two later.

Or just paste the picks and results to Claude in this folder and it does steps 1-3.

## Files

- `brolay_data.json` - the season. One entry per week, four legs per week.
- `brolay_stats.py` - odds math and stats (pure Python, tested).
- `build_report.py` - builds `Brolay_<season>.pdf` from the JSON.
- `Brolay_<season>.pdf` - the latest report, committed so it can be shared straight from the repo.
- `nfl_logo.png` - logo shown at the top of the report. Not in the repo (gitignored);
  drop your own copy next to the script, or the title prints without it.
- `test_brolay_stats.py` - `python -m pytest -q`
- `.github/workflows/pages.yml` - publishes the newest `Brolay_*.pdf` to GitHub Pages
  whenever one is pushed to `main`. It serves the committed PDF; it does not rebuild it.

## Data format

```json
{
  "season": 2026,
  "stake_per_person": 10,
  "members": ["Matt", "Dan", "Dad", "Nick"],
  "weeks": [
    {
      "week": 2,
      "date": "2026-09-20",
      "legs": [
        {
          "person": "Matt",
          "pick": "Green Bay Packers -3.5",
          "opponent": "at New York Jets",
          "type": "spread",
          "odds": -110,
          "result": "miss",
          "score": "Packers 20, Jets 17 (OT)"
        }
      ]
    }
  ]
}
```

Per leg:

- `person` - must match a name in `members`, or the leg won't show up on the leaderboard.
- `pick` - the bet as it reads on the slip.
- `type` - a label for the report (`"spread"`, `"moneyline"`, ...). Not used in the math.
- `odds` - American odds as a whole number: `-110`, `150`.
- `result` - `"hit"`, `"miss"`, `"push"`, or `null` while the game is open.
- `opponent` - optional. `"at New York Jets"` or `"vs Seattle Seahawks"`.
- `score` - optional. Final score, or `null` until the game ends.

Those are the only keys a leg can have; anything else stops the build.

Per week, two optional extras:

- `stake` - total wagered that week, if it isn't the usual $10 x 4.
- `note` - a line of small print at the bottom of that week's page.

## What's in the report

- Page 1: parlay record, wagered, paid out and net, the season leaderboard, and a
  bankroll chart of cumulative net after each settled week.
- Page 2: each person's actual hit rate against what their odds implied, a risk
  ranking by average odds taken, and the awards tally with a week-by-week log.
- Then one page per week, newest first: every leg with its game, odds and result, the
  parlay price and payout, and a one-line verdict.

## Rules baked into the math

- Parlay price = product of each leg's decimal odds. Payout = $40 x that price.
- A push drops that leg from the parlay; the rest still pay. If every leg pushes, the
  week is void and the stake comes back.
- A week is lost the moment any leg misses, even if other legs are still open.
- While a week is open, "Pays" assumes every open leg hits.
- MVP = longest-odds leg that hit. Blown Layup = safest-odds leg that missed.
- Sole anchor = the only miss in a losing week.
- Leaderboard ranks by hit rate on settled legs, ties broken by total hits. Pushes and
  open legs don't count toward hit rate or streaks.
- Net and the bankroll chart count settled weeks only.
