"""
Run this once from your ipl-bets folder:
    python migrate_payouts.py

Recalculates every match's payouts using exact float division
(e.g. 33.33 each instead of 33 / 33 / 34).
Your match history and dates are untouched.
"""

import json, math, os, sys
sys.path.insert(0, os.path.dirname(__file__))

from app import app, db, Match

def recalc_payouts(team1, team2, winner_team, bettors, picks):
    pot     = len(bettors) * 100
    winners = [m for m in bettors if picks.get(m) == winner_team]
    losers  = [m for m in bettors if picks.get(m) != winner_team]
    payouts = {}

    if winner_team in ('none', '') or not winners:
        for m in bettors:
            payouts[m] = 0
    else:
        share = round(pot / len(winners) - 100, 2)
        for m in losers:
            payouts[m] = -100
        for m in winners:
            payouts[m] = share

    return payouts

with app.app_context():
    matches = Match.query.all()
    updated = 0

    for match in matches:
        bettors = json.loads(match.bettors)
        picks   = json.loads(match.picks)

        new_payouts = recalc_payouts(
            match.team1, match.team2,
            match.winner_team,
            bettors, picks
        )

        old = json.loads(match.payouts)
        if old != new_payouts:
            match.payouts = json.dumps(new_payouts)
            updated += 1

    db.session.commit()
    print(f"Done — updated {updated} of {len(matches)} matches.")
