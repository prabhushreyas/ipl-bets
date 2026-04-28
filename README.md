# 🏏 IPL Family Bets

A full-stack Flask web app for tracking your family's IPL betting pool.  
Pre-loaded with all 2026 season results. Add new matches, track P&L, and settle up at the end of the season.

---

## Tech Stack

- **Backend:** Python 3.11 + Flask + SQLAlchemy
- **Database:** SQLite (dev) / PostgreSQL (prod)
- **Frontend:** Vanilla JS + CSS (no frameworks, single-page feel)

---

## Local Setup

### 1. Clone / unzip the project

```bash
cd ipl-bets
```

### 2. Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment (optional)

```bash
cp .env.example .env
# Edit .env if you want a custom SECRET_KEY
```

### 5. Run the development server

```bash
python app.py
```

Open **http://localhost:5000** in your browser.

The database is created automatically on first run and seeded with all historical IPL 2026 match data.

---

## Deploying to Render (free tier)

1. Push the project to a GitHub repo.
2. Go to [render.com](https://render.com) → New → Web Service.
3. Connect your repo.
4. Set:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
5. Add environment variables:
   - `SECRET_KEY` → any random string
   - `DATABASE_URL` → your PostgreSQL connection string (add a Render Postgres database)
6. Deploy.

---

## Deploying to Heroku

```bash
heroku create your-ipl-bets
heroku addons:create heroku-postgresql:mini
git push heroku main
heroku config:set SECRET_KEY=your-random-secret
heroku open
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Main app (HTML) |
| GET | `/api/matches` | All matches (newest first) |
| POST | `/api/matches` | Record a new match |
| DELETE | `/api/matches/<id>` | Delete a match |
| DELETE | `/api/matches/clear` | Delete ALL matches |
| GET | `/api/stats` | Leaderboard + season stats |
| GET | `/api/members` | List of members |
| GET | `/health` | Health check |

### POST `/api/matches` — Request body

```json
{
  "team1": "MI",
  "team2": "CSK",
  "winner_team": "t1",
  "bettors": ["Umesh", "Sheetal", "Shreyas", "Shreshta"],
  "picks": {
    "Umesh":   "t1",
    "Sheetal": "t2",
    "Shreyas": "t1",
    "Shreshta":"t2"
  },
  "match_date": "2026-04-26"
}
```

---

## Members

Hardcoded in `app.py` as `MEMBERS = ['Umesh', 'Sheetal', 'Shreyas', 'Shreshta']`.  
To add/remove members, update this list and restart the server.

---

## Payout Logic

- Each bettor puts in ₹100.
- Winners split the pot evenly (integer-safe: remainder distributed one rupee at a time).
- Net P&L = winnings − ₹100 stake.
- Example — 3 winners out of 4 bettors (₹400 pot): each winner gets ₹133 gross → net **+₹33/+₹34**, loser **−₹100**.
