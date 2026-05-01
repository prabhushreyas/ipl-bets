from flask import Flask, jsonify, request, render_template, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime
from functools import wraps
import os
import json
import requests as http_requests

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL',
    f'sqlite:///{os.path.join(BASE_DIR, "ipl_bets.db")}'
).replace('postgres://', 'postgresql://')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'ipl-bets-dev-secret-change-me')

db = SQLAlchemy(app)
ADMIN_PASSWORD  = os.environ.get('ADMIN_PASSWORD', 'ipl2026admin')
ODDS_API_KEY    = os.environ.get('ODDS_API_KEY', '')
RAPIDAPI_KEY    = os.environ.get('RAPIDAPI_KEY', '')

# Map short team codes → full names used by APIs
IPL_TEAM_NAMES = {
    'MI':   'Mumbai Indians',
    'CSK':  'Chennai Super Kings',
    'RCB':  'Royal Challengers Bengaluru',
    'KKR':  'Kolkata Knight Riders',
    'DC':   'Delhi Capitals',
    'SRH':  'Sunrisers Hyderabad',
    'RR':   'Rajasthan Royals',
    'PBKS': 'Punjab Kings',
    'GT':   'Gujarat Titans',
    'LSG':  'Lucknow Super Giants',
}

def expand_team(code):
    return IPL_TEAM_NAMES.get(code.upper(), code)

def fetch_odds_once(team1, team2):
    """Fetch win probability % for each team from The Odds API — called once when match opens."""
    if not ODDS_API_KEY:
        return {'team1_odds': 'N/A', 'team2_odds': 'N/A'}
    try:
        url = (
            'https://api.the-odds-api.com/v4/sports/cricket_ipl/odds/'
            f'?apiKey={ODDS_API_KEY}&regions=eu&markets=h2h&oddsFormat=decimal'
        )
        resp = http_requests.get(url, timeout=8)
        resp.raise_for_status()
        matches = resp.json()

        t1_full = expand_team(team1).lower()
        t2_full = expand_team(team2).lower()

        for m in matches:
            home = m.get('home_team', '').lower()
            away = m.get('away_team', '').lower()
            if (t1_full in home or t1_full in away or team1.lower() in home or team1.lower() in away):
                bookmakers = m.get('bookmakers', [])
                if not bookmakers:
                    break
                outcomes = bookmakers[0]['markets'][0]['outcomes']
                odds_map = {o['name'].lower(): o['price'] for o in outcomes}

                def win_pct(name):
                    for k, v in odds_map.items():
                        if name.lower() in k:
                            return str(round((1 / v) * 100)) + '%'
                    return 'N/A'

                return {
                    'team1_odds': win_pct(t1_full) if win_pct(t1_full) != 'N/A' else win_pct(team1),
                    'team2_odds': win_pct(t2_full) if win_pct(t2_full) != 'N/A' else win_pct(team2),
                }
    except Exception as e:
        print(f'[odds] fetch failed: {e}')
    return {'team1_odds': 'N/A', 'team2_odds': 'N/A'}


def fetch_team_stats(team1, team2):
    """Fetch IPL season stats (form, W/L record) for both teams via Cricbuzz on RapidAPI."""
    if not RAPIDAPI_KEY:
        return {'team1_stats': None, 'team2_stats': None}
    try:
        headers = {
            'X-RapidAPI-Key':  RAPIDAPI_KEY,
            'X-RapidAPI-Host': 'cricbuzz-cricket.p.rapidapi.com',
        }
        # Get list of series to find current IPL series ID
        series_resp = http_requests.get(
            'https://cricbuzz-cricket.p.rapidapi.com/series/v1/international',
            headers=headers, timeout=8
        )
        series_resp.raise_for_status()
        series_data = series_resp.json()

        ipl_id = None
        for group in series_data.get('seriesMapProto', []):
            for series in group.get('series', []):
                if 'ipl' in series.get('name', '').lower() or 'indian premier' in series.get('name', '').lower():
                    ipl_id = series.get('id')
                    break
            if ipl_id:
                break

        if not ipl_id:
            # Try domestic series list
            dom_resp = http_requests.get(
                'https://cricbuzz-cricket.p.rapidapi.com/series/v1/domestic',
                headers=headers, timeout=8
            )
            dom_resp.raise_for_status()
            dom_data = dom_resp.json()
            for group in dom_data.get('seriesMapProto', []):
                for series in group.get('series', []):
                    if 'ipl' in series.get('name', '').lower():
                        ipl_id = series.get('id')
                        break
                if ipl_id:
                    break

        if not ipl_id:
            return {'team1_stats': None, 'team2_stats': None}

        # Get matches for the IPL series
        matches_resp = http_requests.get(
            f'https://cricbuzz-cricket.p.rapidapi.com/series/v1/{ipl_id}/matches',
            headers=headers, timeout=8
        )
        matches_resp.raise_for_status()
        match_list = matches_resp.json()

        def calc_stats(team_code):
            full = expand_team(team_code)
            wins, losses, form = 0, 0, []
            for match_item in match_list.get('matchDetails', []):
                for match in match_item.get('matchDetailsMap', {}).get('match', []):
                    info = match.get('matchInfo', {})
                    result = match.get('matchScore', {})
                    state = info.get('state', '')
                    if state != 'Complete':
                        continue
                    t1_name = info.get('team1', {}).get('teamName', '')
                    t2_name = info.get('team2', {}).get('teamName', '')
                    involved = (team_code.upper() in t1_name.upper() or team_code.upper() in t2_name.upper() or
                                full.lower() in t1_name.lower() or full.lower() in t2_name.lower())
                    if not involved:
                        continue
                    winner_id = info.get('matchWinner', '')
                    t1_id = str(info.get('team1', {}).get('teamId', ''))
                    t2_id = str(info.get('team2', {}).get('teamId', ''))
                    team_id = t1_id if (team_code.upper() in t1_name.upper() or full.lower() in t1_name.lower()) else t2_id
                    if str(winner_id) == team_id:
                        wins += 1
                        form.append('W')
                    else:
                        losses += 1
                        form.append('L')

            form_last5 = form[-5:] if len(form) >= 5 else form
            return {
                'wins':   wins,
                'losses': losses,
                'played': wins + losses,
                'form':   ' '.join(form_last5) if form_last5 else 'No data',
            }

        return {
            'team1_stats': calc_stats(team1),
            'team2_stats': calc_stats(team2),
        }
    except Exception as e:
        print(f'[stats] fetch failed: {e}')
    return {'team1_stats': None, 'team2_stats': None}

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Admin access required'}), 403
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated

# ── Models ───────────────────────────────────────────────────────────────────
class Match(db.Model):
    __tablename__ = 'matches'
    id          = db.Column(db.Integer, primary_key=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    match_date  = db.Column(db.String(20), nullable=False)
    team1       = db.Column(db.String(50), nullable=False)
    team2       = db.Column(db.String(50), nullable=False)
    winner_team = db.Column(db.String(10), nullable=False)
    winner_name = db.Column(db.String(50), nullable=False)
    pot         = db.Column(db.Integer, nullable=False)
    bettors     = db.Column(db.Text, nullable=False)
    picks       = db.Column(db.Text, nullable=False)
    payouts     = db.Column(db.Text, nullable=False)
    seeded      = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            'id': self.id, 'match_date': self.match_date,
            'team1': self.team1, 'team2': self.team2,
            'winner_team': self.winner_team, 'winner_name': self.winner_name,
            'pot': self.pot, 'bettors': json.loads(self.bettors),
            'picks': json.loads(self.picks), 'payouts': json.loads(self.payouts),
            'seeded': self.seeded,
        }


class ActiveMatch(db.Model):
    """A pending match open for picking. Multiple can coexist."""
    __tablename__ = 'active_match'
    id             = db.Column(db.Integer, primary_key=True)
    match_date     = db.Column(db.String(20), nullable=False)
    team1          = db.Column(db.String(50), nullable=False)
    team2          = db.Column(db.String(50), nullable=False)
    picks          = db.Column(db.Text, nullable=False, default='{}')
    bettors        = db.Column(db.Text, nullable=False, default='[]')
    teams_revealed = db.Column(db.Boolean, nullable=False, default=False)
    # odds+stats stored in existing picks column under reserved key '_meta'
    # NO new columns needed — zero migration required

    def to_dict(self, is_admin=False, viewer_name=None):
        picks_data = json.loads(self.picks)
        bettors    = json.loads(self.bettors)
        show_picks = is_admin or self.teams_revealed
        # Extract _meta (odds+stats) then strip it from picks shown to users
        meta       = picks_data.pop('_meta', {})
        return {
            'id':             self.id,
            'match_date':     self.match_date,
            'team1':          self.team1,
            'team2':          self.team2,
            'bettors':        bettors,
            'picked_count':   len(picks_data),
            'total_bettors':  len(bettors),
            'pot':            len(picks_data) * 100,
            'picked_names':   list(picks_data.keys()),
            'picks':          picks_data if show_picks else {},
            'teams_revealed': self.teams_revealed,
            'i_have_picked':  (viewer_name in picks_data) if viewer_name else False,
            'team1_odds':     meta.get('team1_odds', 'N/A'),
            'team2_odds':     meta.get('team2_odds', 'N/A'),
            'match_stats':    meta.get('match_stats', None),
        }


MEMBERS = ['Umesh', 'Sheetal', 'Shreyas', 'Shreshta']

SEED_MATCHES = [
    {'match': 'RCB vs SRH',  'w': 'SRH',  'p': {'Umesh': -100, 'Sheetal':  33.33, 'Shreyas':  33.33, 'Shreshta':  33.34}},
    {'match': 'MI vs KKR',   'w': 'MI',   'p': {'Umesh':  33.33, 'Sheetal':  33.33, 'Shreyas': -100, 'Shreshta':  33.34}},
    {'match': 'RR vs CSK',   'w': 'CSK',  'p': {'Umesh': -100, 'Sheetal': -100, 'Shreyas': 100, 'Shreshta': 100}},
    {'match': 'GT vs PBKS',  'w': 'GT',   'p': {'Umesh': -100, 'Sheetal':  100, 'Shreyas': 100, 'Shreshta': -100}},
    {'match': 'LSG vs DC',   'w': 'LSG',  'p': {'Umesh':  33.33, 'Sheetal':  33.33, 'Shreyas': -100, 'Shreshta':  33.34}},
    {'match': 'SRH vs KKR',  'w': 'SRH',  'p': {'Umesh':  33.33, 'Sheetal':  33.33, 'Shreyas':  33.34, 'Shreshta': -100}},
    {'match': 'CSK vs PBKS', 'w': 'CSK',  'p': {'Umesh': -100, 'Sheetal': -100, 'Shreyas': 300, 'Shreshta': -100}},
    {'match': 'MI vs DC',    'w': 'MI',   'p': {'Umesh': -100, 'Sheetal':  100, 'Shreyas': 100, 'Shreshta': -100}},
    {'match': 'RR vs GT',    'w': 'RR',   'p': {'Umesh':  33.33, 'Sheetal':  33.33, 'Shreyas':  33.34, 'Shreshta': -100}},
    {'match': 'SRH vs LSG',  'w': 'SRH',  'p': {'Umesh': -100, 'Sheetal': -100, 'Shreyas': 100, 'Shreshta': 100}},
    {'match': 'RCB vs CSK',  'w': 'CSK',  'p': {'Umesh': -100, 'Sheetal':  100, 'Shreyas': 100, 'Shreshta': -100}},
    {'match': 'RR vs MI',    'w': 'MI',   'p': {'Umesh': -100, 'Sheetal':  300, 'Shreyas': -100, 'Shreshta': -100}},
    {'match': 'GT vs DC',    'w': 'DC',   'p': {'Umesh': -100, 'Sheetal': -100, 'Shreyas': -100, 'Shreshta': 300}},
    {'match': 'KKR vs LSG',  'w': 'KKR',  'p': {'Umesh': -100, 'Sheetal':  300, 'Shreyas': -100, 'Shreshta': -100}},
    {'match': 'RCB vs RR',   'w': 'RCB',  'p': {'Umesh':  100, 'Sheetal': -100, 'Shreyas': -100, 'Shreshta': 100}},
    {'match': 'SRH vs PBKS', 'w': 'SRH',  'p': {'Umesh':  300, 'Sheetal': -100, 'Shreyas': -100, 'Shreshta': -100}},
    {'match': 'CSK vs DC',   'w': '—',    'p': {'Umesh':    0, 'Sheetal':    0, 'Shreyas':   0, 'Shreshta':   0}},
    {'match': 'LSG vs GT',   'w': 'LSG',  'p': {'Umesh':  100, 'Sheetal': -100, 'Shreyas': -100, 'Shreshta': 100}},
    {'match': 'RCB vs MI',   'w': 'MI',   'p': {'Umesh': -100, 'Sheetal':  100, 'Shreyas': 100, 'Shreshta': -100}},
    {'match': 'SRH vs RR',   'w': 'RR',   'p': {'Umesh': -100, 'Sheetal': -100, 'Shreyas': -100, 'Shreshta': 300}},
    {'match': 'CSK vs KKR',  'w': 'KKR',  'p': {'Umesh': -100, 'Sheetal':  100, 'Shreyas': 100, 'Shreshta': -100}},
    {'match': 'LSG vs RCB',  'w': 'RCB',  'p': {'Umesh': -100, 'Sheetal':  33.33, 'Shreyas':  33.33, 'Shreshta':  33.34}},
    {'match': 'MI vs PBKS',  'w': 'MI',   'p': {'Umesh': -100, 'Sheetal':  300, 'Shreyas': -100, 'Shreshta': -100}},
    {'match': 'GT vs KKR',   'w': 'KKR',  'p': {'Umesh': -100, 'Sheetal':  33.33, 'Shreyas':  33.33, 'Shreshta':  33.34}},
    {'match': 'RCB vs DC',   'w': 'DC',   'p': {'Umesh': -100, 'Sheetal': -100, 'Shreyas': -100, 'Shreshta': 300}},
    {'match': 'SRH vs CSK',  'w': 'SRH',  'p': {'Umesh': -100, 'Sheetal':  33.33, 'Shreyas':  33.33, 'Shreshta':  33.34}},
    {'match': 'RR vs KKR',   'w': 'RR',   'p': {'Umesh':  100, 'Sheetal': -100, 'Shreyas': -100, 'Shreshta': 100}},
    {'match': 'PBKS vs LSG', 'w': 'PBKS', 'p': {'Umesh':  33.33, 'Sheetal':  33.33, 'Shreyas':  33.34, 'Shreshta': -100}},
    {'match': 'MI vs GT',    'w': 'GT',   'p': {'Umesh':  33.33, 'Sheetal': -100, 'Shreyas':  33.33, 'Shreshta':  33.34}},
    {'match': 'SRH vs DC',   'w': 'SRH',  'p': {'Umesh':  100, 'Sheetal': -100, 'Shreyas': -100, 'Shreshta': 100}},
    {'match': 'RR vs LSG',   'w': 'RR',   'p': {'Umesh':  33.33, 'Sheetal':  33.33, 'Shreyas': -100, 'Shreshta':  33.34}},
    {'match': 'MI vs CSK',   'w': 'CSK',  'p': {'Umesh': -100, 'Sheetal':  100, 'Shreyas': 100, 'Shreshta': -100}},
    {'match': 'RCB vs GT',   'w': 'GT',   'p': {'Umesh':  33.33, 'Sheetal':  33.33, 'Shreyas':  33.34, 'Shreshta': -100}},
    {'match': 'PBKS vs DC',  'w': 'PBKS', 'p': {'Umesh':  33.33, 'Sheetal':  33.33, 'Shreyas':  33.34, 'Shreshta': -100}},
    {'match': 'RR vs SRH',   'w': 'RR',   'p': {'Umesh':  33.33, 'Sheetal':  33.33, 'Shreyas':  33.34, 'Shreshta': -100}},
]


def seed_database():
    if Match.query.count() > 0:
        return
    for s in SEED_MATCHES:
        t1, t2    = s['match'].split(' vs ')
        bettors   = list(s['p'].keys())
        picks_map = {m: ('t1' if s['p'][m] > -100 else 't2') for m in bettors}
        m = Match(
            match_date='2026-03-22', team1=t1, team2=t2,
            winner_team='t1', winner_name=s['w'],
            pot=len(bettors) * 100,
            bettors=json.dumps(bettors), picks=json.dumps(picks_map),
            payouts=json.dumps(s['p']), seeded=True,
        )
        db.session.add(m)
    db.session.commit()


def get_rounded_nets():
    nets = {m: 0.0 for m in MEMBERS}
    for match in Match.query.all():
        payouts = json.loads(match.payouts)
        for m in json.loads(match.bettors):
            nets[m] += payouts.get(m, 0)
    return {m: round(v) for m, v in nets.items()}


def compute_payouts(bettors, picks, winner_t, t1, t2):
    pot     = len(bettors) * 100
    winners = [m for m in bettors if picks.get(m) == winner_t]
    losers  = [m for m in bettors if picks.get(m) != winner_t]
    payouts = {}
    if winner_t == 'none' or not winners:
        for m in bettors: payouts[m] = 0
        winner_name = '—'
    else:
        winner_name = t1 if winner_t == 't1' else t2
        share = round(pot / len(winners) - 100, 2)
        for m in losers:  payouts[m] = -100
        for m in winners: payouts[m] = share
    return payouts, winner_name


# ── Auth routes ───────────────────────────────────────────────────────────────
@app.route('/api/login', methods=['POST'])
def do_login():
    data = request.get_json(force=True)
    if data.get('password', '') != ADMIN_PASSWORD:
        return jsonify({'error': 'Invalid password'}), 401
    session['role'] = 'admin'
    return jsonify({'role': 'admin'})

@app.route('/api/logout', methods=['POST'])
def do_logout():
    session.clear()
    return jsonify({'ok': True})

@app.route('/api/me')
def me():
    return jsonify({'role': session.get('role', 'guest')})

@app.route('/')
def index():
    return render_template('index.html', members=MEMBERS, role=session.get('role', 'guest'))


# ── Active matches ────────────────────────────────────────────────────────────
@app.route('/api/active-matches', methods=['GET'])
def get_active_matches():
    is_admin    = session.get('role') == 'admin'
    viewer_name = request.args.get('name', '')
    matches     = ActiveMatch.query.order_by(ActiveMatch.id).all()
    return jsonify([m.to_dict(is_admin=is_admin, viewer_name=viewer_name) for m in matches])


@app.route('/api/active-matches', methods=['POST'])
@admin_required
def create_active_match():
    data    = request.get_json(force=True)
    t1      = data.get('team1', '').strip()
    t2      = data.get('team2', '').strip()
    date    = data.get('match_date', datetime.utcnow().strftime('%Y-%m-%d'))
    bettors = data.get('bettors', MEMBERS)
    if not t1 or not t2:
        return jsonify({'error': 'Both team names required'}), 400

    # Fetch odds and stats once — store in picks under reserved '_meta' key
    # This avoids any DB migration (no new columns needed)
    odds  = fetch_odds_once(t1, t2)
    stats = fetch_team_stats(t1, t2)
    meta  = {
        '_meta': {
            'team1_odds':  odds['team1_odds'],
            'team2_odds':  odds['team2_odds'],
            'match_stats': stats,
        }
    }

    am = ActiveMatch(
        match_date=date, team1=t1, team2=t2,
        picks=json.dumps(meta), bettors=json.dumps(bettors),
    )
    db.session.add(am)
    db.session.commit()
    return jsonify(am.to_dict(is_admin=True)), 201


@app.route('/api/active-matches/<int:match_id>/pick', methods=['POST'])
def submit_pick(match_id):
    am      = ActiveMatch.query.get_or_404(match_id)
    data    = request.get_json(force=True)
    name    = data.get('name', '').strip()
    choice  = data.get('pick', '')
    bettors = json.loads(am.bettors)

    if name not in MEMBERS:
        return jsonify({'error': 'Unknown name'}), 400
    if name not in bettors:
        return jsonify({'error': 'You are not in this match'}), 400
    if choice not in ('t1', 't2', 'none'):
        return jsonify({'error': 'Pick must be t1, t2, or none'}), 400

    picks       = json.loads(am.picks)
    is_change   = name in picks and name != '_meta'
    picks[name] = choice
    am.picks    = json.dumps(picks)
    db.session.commit()

    return jsonify({
        'ok': True, 'is_change': is_change,
        'picked_count': len(picks), 'total_bettors': len(bettors),
        'pot': len(picks) * 100, 'picked_names': list(picks.keys()),
    })


@app.route('/api/active-matches/<int:match_id>/finalize', methods=['POST'])
@admin_required
def finalize_match(match_id):
    am       = ActiveMatch.query.get_or_404(match_id)
    data     = request.get_json(force=True)
    winner_t = data.get('winner_team')
    if winner_t not in ('t1', 't2', 'none'):
        return jsonify({'error': 'winner_team must be t1, t2, or none'}), 400

    picks          = json.loads(am.picks)
    bettors        = json.loads(am.bettors)
    active_bettors = [m for m in bettors if m in picks]
    if not active_bettors:
        return jsonify({'error': 'No one has picked yet'}), 400

    payouts, winner_name = compute_payouts(active_bettors, picks, winner_t, am.team1, am.team2)
    match = Match(
        match_date=am.match_date, team1=am.team1, team2=am.team2,
        winner_team=winner_t, winner_name=winner_name,
        pot=len(active_bettors) * 100,
        bettors=json.dumps(active_bettors), picks=json.dumps(picks),
        payouts=json.dumps(payouts), seeded=False,
    )
    db.session.add(match)
    db.session.delete(am)
    db.session.commit()
    return jsonify(match.to_dict())


@app.route('/api/active-matches/<int:match_id>/reveal', methods=['PATCH'])
@admin_required
def toggle_reveal(match_id):
    am = ActiveMatch.query.get_or_404(match_id)
    data = request.get_json(force=True)
    am.teams_revealed = bool(data.get('revealed', False))
    db.session.commit()
    return jsonify({'ok': True, 'teams_revealed': am.teams_revealed})


@app.route('/api/active-matches/<int:match_id>', methods=['DELETE'])
@admin_required
def cancel_active_match(match_id):
    am = ActiveMatch.query.get_or_404(match_id)
    db.session.delete(am)
    db.session.commit()
    return jsonify({'ok': True})


# ── Completed matches ─────────────────────────────────────────────────────────
@app.route('/api/matches', methods=['GET'])
def get_matches():
    return jsonify([m.to_dict() for m in Match.query.order_by(Match.id.desc()).all()])

@app.route('/api/matches/<int:match_id>', methods=['DELETE'])
@admin_required
def delete_match(match_id):
    match = Match.query.get_or_404(match_id)
    db.session.delete(match); db.session.commit()
    return jsonify({'deleted': match_id})

@app.route('/api/matches/clear', methods=['DELETE'])
@admin_required
def clear_all():
    Match.query.delete(); db.session.commit()
    return jsonify({'cleared': True})


@app.route('/api/stats')
def get_stats():
    nets        = get_rounded_nets()
    total       = Match.query.count()
    sorted_nets = sorted(nets.items(), key=lambda x: -x[1])
    top         = sorted_nets[0] if sorted_nets else (None, 0)
    games_by = {m: 0 for m in MEMBERS}
    wins_by  = {m: 0 for m in MEMBERS}
    loss_by  = {m: 0 for m in MEMBERS}
    for match in Match.query.all():
        bettors = json.loads(match.bettors)
        payouts = json.loads(match.payouts)
        for m in bettors:
            games_by[m] += 1
            if payouts.get(m, 0) > 0:   wins_by[m] += 1
            elif payouts.get(m, 0) < 0: loss_by[m] += 1
    leaderboard = sorted([{
        'name': m, 'net': nets.get(m, 0), 'games': games_by[m],
        'wins': wins_by[m], 'losses': loss_by[m],
        'win_pct': round(wins_by[m] / games_by[m] * 100) if games_by[m] else 0,
    } for m in MEMBERS], key=lambda x: -x['net'])
    return jsonify({
        'total_matches': total, 'top_earner': top[0], 'best_net': top[1],
        'nets': nets, 'leaderboard': leaderboard,
    })

@app.route('/api/members')
def get_members():
    return jsonify(MEMBERS)

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})


with app.app_context():
    db.create_all()
    seed_database()

if __name__ == '__main__':
    port  = int(os.environ.get('PORT', 5001))
    debug = os.environ.get('FLASK_ENV', 'development') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)
