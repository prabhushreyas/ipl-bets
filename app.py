/* ── State ───────────────────────────────────────────────────────────────── */
const API      = '';
let currentRole    = 'guest';
let allMembers     = [];
let myName         = null;   // selected identity
let selectedMatch  = null;   // selected active match object
let activeMatches  = [];     // all open matches
let adminWinners   = {};     // {matchId: 't1'|'t2'|'none'}

/* ── Bootstrap ───────────────────────────────────────────────────────────── */
window.addEventListener('DOMContentLoaded', async () => {
  allMembers = [...document.querySelectorAll('#memberToggles .toggle-btn')].map(b => b.dataset.name);
  const today = new Date().toISOString().split('T')[0];
  const dateEl = document.getElementById('matchDate');
  if (dateEl) dateEl.value = today;

  await syncRole();
  await loadStats();
  setConnStatus(true);
});

/* ── Role ────────────────────────────────────────────────────────────────── */
async function syncRole() {
  try {
    const data = await apiFetch('/api/me');
    currentRole = data.role || 'guest';
  } catch (_) { currentRole = 'guest'; }
  await applyRoleUI();
}

async function applyRoleUI() {
  const isAdmin = currentRole === 'admin';
  document.getElementById('adminLoginBtn').style.display = isAdmin ? 'none' : 'flex';
  document.getElementById('adminBadge').style.display    = isAdmin ? 'flex' : 'none';
  if (isAdmin) {
    document.getElementById('guestFlow').style.display    = 'none';
    document.getElementById('adminBetPanel').style.display = 'block';
    await renderAdminBetTab();
  } else {
    document.getElementById('guestFlow').style.display    = 'block';
    document.getElementById('adminBetPanel').style.display = 'none';
    await renderGuestBetTab();
  }
}

/* ── API helpers ─────────────────────────────────────────────────────────── */
async function apiFetch(path, opts = {}) {
  const res = await fetch(API + path, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    ...opts,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || 'HTTP ' + res.status);
  }
  return res.json();
}

function setConnStatus(ok) {
  const el = document.getElementById('connStatus');
  el.textContent = ok ? '● Connected' : '● Offline';
  el.className   = 'conn-status ' + (ok ? 'ok' : 'err');
}

/* ── Stats ───────────────────────────────────────────────────────────────── */
async function loadStats() {
  try {
    const s = await apiFetch('/api/stats');
    document.getElementById('s-matches').textContent = s.total_matches;
    document.getElementById('s-top').textContent     = s.top_earner || '—';
    const bestEl = document.getElementById('s-best');
    const best   = s.best_net || 0;
    bestEl.textContent = (best >= 0 ? '+₹' : '-₹') + Math.abs(best);
    bestEl.className   = 'stat-value ' + (best > 0 ? 'green' : best < 0 ? 'red' : '');
    setConnStatus(true);
  } catch (e) { setConnStatus(false); }
}

/* ── Tabs ────────────────────────────────────────────────────────────────── */
function switchTab(t) {
  ['bet', 'history', 'leaderboard', 'settings'].forEach((x, i) => {
    document.getElementById('tab-' + x).style.display = x === t ? 'block' : 'none';
    document.querySelectorAll('.tab')[i].classList.toggle('active', x === t);
  });
  if (t === 'history')     renderHistory();
  if (t === 'leaderboard') renderLeaderboard();
  if (t === 'settings')    renderSettings();
}

function renderSettings() {
  const isAdmin = currentRole === 'admin';
  document.getElementById('settingsGuestNotice').style.display = isAdmin ? 'none'  : 'block';
  document.getElementById('settingsAdminPanel').style.display  = isAdmin ? 'block' : 'none';
}

/* ══════════════════════════════════════════════════════════════════════════════
   GUEST FLOW  — 3 steps: match → name → pick
══════════════════════════════════════════════════════════════════════════════ */

async function renderGuestBetTab() {
  try {
    const qs = myName ? '?name=' + encodeURIComponent(myName) : '';
    activeMatches = await apiFetch('/api/active-matches' + qs);
  } catch (_) { activeMatches = []; }

  if (!activeMatches.length) {
    showOnly('noMatchGuest');
    return;
  }

  // If we had a selected match, refresh it
  if (selectedMatch) {
    const refreshed = activeMatches.find(m => m.id === selectedMatch.id);
    if (refreshed) selectedMatch = refreshed;
    else { selectedMatch = null; myName = null; }
  }

  if (!selectedMatch) {
    showGuestStep('matchSelectPanel');
    renderMatchSelectGrid();
  } else if (selectedMatch.teams_revealed) {
    showGuestStep('pickPanel');
    renderPickPanel();
  } else if (!myName) {
    showGuestStep('identityPanel');
    renderIdentityPanel();
  } else {
    showGuestStep('pickPanel');
    renderPickPanel();
  }
}

function showOnly(id) {
  ['noMatchGuest', 'matchSelectPanel', 'identityPanel', 'pickPanel'].forEach(x => {
    document.getElementById(x).style.display = 'none';
  });
  document.getElementById(id).style.display = 'block';
}

function showGuestStep(id) { showOnly(id); }

function renderMatchSelectGrid() {
  const grid = document.getElementById('matchSelectGrid');
  grid.innerHTML = activeMatches.map(m => {
    const date  = fmtDate(m.match_date);
    const prog  = m.picked_count + '/' + m.total_bettors + ' picked';
    const revealedBadge = m.teams_revealed
      ? '<span style="font-size:11px;font-weight:600;padding:2px 8px;border-radius:20px;' +
        'background:var(--green-bg);color:var(--green);border:1px solid rgba(45,186,135,0.35);' +
        'margin-left:8px;">👁 Revealed</span>'
      : '';
    return `
      <button class="match-select-btn" onclick="selectMatch(${m.id})">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;">
          <div>
            <div style="font-family:'Syne',sans-serif;font-size:16px;font-weight:700;color:var(--text);display:flex;align-items:center;flex-wrap:wrap;gap:4px;">
              ${m.team1} <span style="color:var(--text3);font-weight:400;">vs</span> ${m.team2}${revealedBadge}
            </div>
            <div style="font-size:12px;color:var(--text3);margin-top:3px;">${date}</div>
          </div>
          <div style="text-align:right;flex-shrink:0;">
            <div style="font-family:'Syne',sans-serif;font-size:15px;font-weight:700;color:var(--green);">₹${m.pot}</div>
            <div style="font-size:11px;color:var(--text3);margin-top:2px;">${prog}</div>
          </div>
        </div>
      </button>`;
  }).join('');
}

function selectMatch(id) {
  selectedMatch = activeMatches.find(m => m.id === id) || null;
  myName = null;
  if (selectedMatch && selectedMatch.teams_revealed) {
    showGuestStep('pickPanel');
    renderPickPanel();
  } else {
    showGuestStep('identityPanel');
    renderIdentityPanel();
  }
}

function backToMatchSelect() {
  selectedMatch = null;
  myName = null;
  showGuestStep('matchSelectPanel');
  renderMatchSelectGrid();
}

function renderIdentityPanel() {
  if (!selectedMatch) return;
  document.getElementById('identityMatchLabel').textContent =
    selectedMatch.team1 + ' vs ' + selectedMatch.team2;
}

function selectIdentity(name) {
  myName = name;
  // Refresh match with viewer context
  apiFetch('/api/active-matches?name=' + encodeURIComponent(name)).then(matches => {
    const fresh = matches.find(m => m.id === selectedMatch.id);
    if (fresh) selectedMatch = fresh;
    showGuestStep('pickPanel');
    renderPickPanel();
  });
}

function backToIdentity() {
  myName = null;
  showGuestStep('identityPanel');
  renderIdentityPanel();
}

function pickBack() {
  // If teams are revealed, skip identity panel and go back to match select
  if (selectedMatch && selectedMatch.teams_revealed) {
    backToMatchSelect();
  } else {
    backToIdentity();
  }
}

function renderPickPanel() {
  if (!selectedMatch) return;

  const isRevealed = !!selectedMatch.teams_revealed;

  // Header: greeting or match title
  if (myName) {
    document.getElementById('pickGreeting').textContent = 'Hey ' + myName + '! 👋';
  } else {
    document.getElementById('pickGreeting').textContent = selectedMatch.team1 + ' vs ' + selectedMatch.team2;
  }
  document.getElementById('pickSubtitle').textContent =
    (myName ? selectedMatch.team1 + ' vs ' + selectedMatch.team2 + ' · ' : '') + fmtDate(selectedMatch.match_date);

  document.getElementById('livePot').textContent = '₹' + selectedMatch.pot;
  document.getElementById('pickProgress').textContent =
    selectedMatch.picked_count + ' of ' + selectedMatch.total_bettors + ' picked';

  const revealedNotice = document.getElementById('revealedNotice');
  const alreadyEl      = document.getElementById('alreadyPickedNotice');
  const pickBtnsEl     = document.getElementById('guestPickButtons');

  if (isRevealed) {
    revealedNotice.style.display = 'flex';
    alreadyEl.style.display      = 'none';
    pickBtnsEl.style.display     = 'none';
    document.getElementById('pickT1Btn').textContent = selectedMatch.team1;
    document.getElementById('pickT2Btn').textContent = selectedMatch.team2;
  } else {
    revealedNotice.style.display = 'none';
    document.getElementById('pickT1Btn').textContent = selectedMatch.team1;
    document.getElementById('pickT2Btn').textContent = selectedMatch.team2;
    document.getElementById('pickT1Btn').disabled = false;
    document.getElementById('pickT2Btn').disabled = false;
    document.getElementById('pickNoneBtn').disabled = false;

    const iHavePicked = selectedMatch.i_have_picked;
    if (iHavePicked) {
      pickBtnsEl.style.display = 'none';
      alreadyEl.style.display  = 'block';
      const pickLabel = document.getElementById('currentPickLabel');
      if (pickLabel) pickLabel.textContent = 'Team chosen ✓  — waiting for match result.';
    } else {
      alreadyEl.style.display  = 'none';
      pickBtnsEl.style.display = 'block';
    }
  }

  // ── Odds & Stats card ──────────────────────────────────────────────────────
  let oddsStatsEl = document.getElementById('oddsStatsCard');
  if (!oddsStatsEl) {
    oddsStatsEl = document.createElement('div');
    oddsStatsEl.id = 'oddsStatsCard';
    oddsStatsEl.style.cssText = 'margin-top:16px;padding:14px;background:var(--surface2);border:1px solid var(--border);border-radius:var(--radius);';
    // Insert before the "Picked so far" section (last child of pickPanel)
    const pickPanel = document.getElementById('pickPanel');
    const pickedSection = pickPanel.querySelector('[style*="border-top"]');
    if (pickedSection) pickPanel.insertBefore(oddsStatsEl, pickedSection);
    else pickPanel.appendChild(oddsStatsEl);
  }

  const t1odds = selectedMatch.team1_odds || 'N/A';
  const t2odds = selectedMatch.team2_odds || 'N/A';
  const stats  = selectedMatch.match_stats || {};
  const t1s    = stats.team1_stats;
  const t2s    = stats.team2_stats;

  function formBadges(formStr) {
    if (!formStr || formStr === 'No data') return '<span style="color:var(--text3);font-size:11px;">No data</span>';
    return formStr.split(' ').map(r =>
      '<span style="display:inline-block;width:20px;height:20px;line-height:20px;text-align:center;' +
      'border-radius:4px;font-size:10px;font-weight:700;margin-right:2px;' +
      (r === 'W'
        ? 'background:var(--green-bg);color:var(--green);border:1px solid rgba(45,186,135,0.3);'
        : 'background:rgba(232,91,91,0.1);color:var(--red);border:1px solid rgba(232,91,91,0.2);') +
      '">' + r + '</span>'
    ).join('');
  }

  function teamBlock(teamName, odds, s) {
    const record = s ? s.wins + 'W / ' + s.losses + 'L' : '—';
    const form   = s ? formBadges(s.form) : '<span style="color:var(--text3);font-size:11px;">No data</span>';
    return `
      <div style="flex:1;min-width:0;">
        <div style="font-family:'Syne',sans-serif;font-weight:700;font-size:14px;color:var(--text);margin-bottom:6px;">${teamName}</div>
        <div style="font-size:22px;font-weight:800;font-family:'Syne',sans-serif;color:var(--green);margin-bottom:4px;">${odds}</div>
        <div style="font-size:11px;color:var(--text3);margin-bottom:8px;">win probability</div>
        <div style="font-size:12px;color:var(--text2);margin-bottom:4px;">Season: <strong style="color:var(--text);">${record}</strong></div>
        <div style="font-size:11px;color:var(--text3);margin-bottom:4px;">Last 5:</div>
        <div>${form}</div>
      </div>`;
  }

  oddsStatsEl.innerHTML = `
    <div style="font-size:11px;font-weight:600;color:var(--text3);letter-spacing:0.05em;text-transform:uppercase;margin-bottom:12px;">
      📊 Team Stats &amp; Odds
    </div>
    <div style="display:flex;gap:16px;align-items:flex-start;">
      ${teamBlock(selectedMatch.team1, t1odds, t1s)}
      <div style="width:1px;background:var(--border);align-self:stretch;"></div>
      ${teamBlock(selectedMatch.team2, t2odds, t2s)}
    </div>
    <div style="margin-top:10px;font-size:10px;color:var(--text3);text-align:center;">
      Odds fetched at match open · Stats: IPL 2026 season
    </div>`;
  // ── End odds & stats ───────────────────────────────────────────────────────

  renderPickedSoFar();

  const revealBanner = document.getElementById('revealBanner');
  if (revealBanner) revealBanner.style.display = isRevealed ? 'block' : 'none';
}

function changePick() {
  document.getElementById('alreadyPickedNotice').style.display = 'none';
  document.getElementById('guestPickButtons').style.display    = 'block';
  document.getElementById('pickT1Btn').disabled   = false;
  document.getElementById('pickT2Btn').disabled   = false;
  document.getElementById('pickNoneBtn').disabled = false;
}

function renderPickedSoFar() {
  if (!selectedMatch) return;
  const wrap        = document.getElementById('pickedSoFar');
  const pickedCount = selectedMatch.picked_count;
  const total       = selectedMatch.total_bettors;
  const revealed    = !!selectedMatch.teams_revealed;
  const picks       = selectedMatch.picks || {};     // populated when revealed
  const bettors     = selectedMatch.bettors || [];
  wrap.innerHTML    = '';

  if (revealed && bettors.length) {
    // Show named chips with their pick
    bettors.forEach(name => {
      const pick = picks[name];
      const chip = document.createElement('div');
      let pickLabel = '•';
      let bg = 'var(--surface2)', border = 'var(--border)', color = 'var(--text3)';
      if (pick === 't1') { pickLabel = selectedMatch.team1; bg = 'var(--green-bg)'; border = 'rgba(45,186,135,0.4)'; color = 'var(--green)'; }
      if (pick === 't2') { pickLabel = selectedMatch.team2; bg = 'var(--green-bg)'; border = 'rgba(45,186,135,0.4)'; color = 'var(--green)'; }
      if (pick === 'none') { pickLabel = '🤷'; bg = 'rgba(234,179,8,0.1)'; border = 'rgba(234,179,8,0.3)'; color = '#b45309'; }
      Object.assign(chip.style, {
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        padding: '6px 10px', borderRadius: '10px', border: '1px solid ' + border,
        background: bg, minWidth: '56px', gap: '2px',
      });
      chip.innerHTML =
        '<span style="font-size:11px;color:var(--text3);font-weight:500;">' + name + '</span>' +
        '<span style="font-size:12px;font-weight:700;color:' + color + ';">' + (pick ? pickLabel : '—') + '</span>';
      wrap.appendChild(chip);
    });
  } else {
    // Original: anonymous dots
    for (let i = 0; i < total; i++) {
      const dot = document.createElement('div');
      const done = i < pickedCount;
      Object.assign(dot.style, {
        width: '36px', height: '36px', borderRadius: '50%',
        background: done ? 'var(--green-bg)' : 'var(--surface2)',
        border: '1px solid ' + (done ? 'rgba(45,186,135,0.4)' : 'var(--border)'),
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: '16px', color: done ? 'var(--green)' : 'var(--text3)',
      });
      dot.textContent = done ? '✓' : '•';
      wrap.appendChild(dot);
    }
  }

  const label = document.createElement('span');
  Object.assign(label.style, { fontSize: '13px', color: 'var(--text3)', alignSelf: 'center', marginLeft: '4px' });
  label.textContent = pickedCount === total ? 'Everyone picked! Waiting for result…' :
                      (total - pickedCount) + ' still to pick';
  wrap.appendChild(label);
}

async function submitGuestPick(choice) {
  if (!myName || !selectedMatch) return;

  const t1Btn   = document.getElementById('pickT1Btn');
  const t2Btn   = document.getElementById('pickT2Btn');
  const noneBtn = document.getElementById('pickNoneBtn');
  t1Btn.disabled = t2Btn.disabled = noneBtn.disabled = true;

  try {
    const result = await apiFetch('/api/active-matches/' + selectedMatch.id + '/pick', {
      method: 'POST',
      body: JSON.stringify({ name: myName, pick: choice }),
    });

    // Update local match state from pick response
    selectedMatch.picked_count  = result.picked_count;
    selectedMatch.pot           = result.pot;
    selectedMatch.picked_names  = result.picked_names;
    selectedMatch.i_have_picked = true;

    // Re-fetch the full match so picks/teams_revealed are up to date
    try {
      const qs = '?name=' + encodeURIComponent(myName);
      const matches = await apiFetch('/api/active-matches' + qs);
      const fresh = matches.find(m => m.id === selectedMatch.id);
      if (fresh) selectedMatch = fresh;
    } catch (_) {}

    // Show already-picked state — only "Team chosen ✓", not which team
    const pickBtnsEl = document.getElementById('guestPickButtons');
    const alreadyEl  = document.getElementById('alreadyPickedNotice');
    pickBtnsEl.style.display = 'none';
    alreadyEl.style.display  = 'block';

    const pickLabel = document.getElementById('currentPickLabel');
    if (pickLabel) {
      if (choice === 'none') pickLabel.textContent = 'You chose to abstain this match.';
      else                   pickLabel.textContent = 'Team chosen ✓  — waiting for match result.';
    }

    document.getElementById('livePot').textContent = '₹' + result.pot;
    document.getElementById('pickProgress').textContent =
      result.picked_count + ' of ' + result.total_bettors + ' picked';
    renderPickedSoFar();

    const verb = result.is_change ? 'updated' : 'locked in';
    showAlert(myName + '! Your pick is ' + verb + ' 🔒', 'success');
  } catch (e) {
    showAlert('Error: ' + e.message, 'error');
    t1Btn.disabled = t2Btn.disabled = noneBtn.disabled = false;
  }
}

/* ── Poll to refresh pot / pick count for guests ────────────────────────── */
setInterval(async () => {
  if (currentRole !== 'guest' || !selectedMatch) return;
  try {
    const qs      = myName ? '?name=' + encodeURIComponent(myName) : '';
    const matches = await apiFetch('/api/active-matches' + qs);
    const fresh   = matches.find(m => m.id === selectedMatch.id);
    if (!fresh) return;
    const wasRevealed = selectedMatch.teams_revealed;
    selectedMatch = fresh;

    // If teams just got revealed while user is on identity or pick panel, transition
    if (!wasRevealed && fresh.teams_revealed) {
      showGuestStep('pickPanel');
      renderPickPanel();
      return;
    }

    const pickPanel = document.getElementById('pickPanel');
    if (!pickPanel || pickPanel.style.display === 'none') return;
    document.getElementById('livePot').textContent = '₹' + fresh.pot;
    document.getElementById('pickProgress').textContent =
      fresh.picked_count + ' of ' + fresh.total_bettors + ' picked';
    renderPickedSoFar();
    const revealBanner = document.getElementById('revealBanner');
    if (revealBanner) revealBanner.style.display = fresh.teams_revealed ? 'block' : 'none';
    const revealedNotice = document.getElementById('revealedNotice');
    if (revealedNotice) revealedNotice.style.display = fresh.teams_revealed ? 'flex' : 'none';
  } catch (_) {}
}, 4000);

/* ══════════════════════════════════════════════════════════════════════════════
   ADMIN BET FLOW
══════════════════════════════════════════════════════════════════════════════ */

async function renderAdminBetTab() {
  try {
    activeMatches = await apiFetch('/api/active-matches');
  } catch (_) { activeMatches = []; }
  renderAdminMatchList();
}

function renderAdminMatchList() {
  const container = document.getElementById('adminActiveMatchList');
  if (!activeMatches.length) {
    container.innerHTML = '';
    return;
  }

  container.innerHTML = activeMatches.map(m => {
    const picks   = m.picks || {};
    const bettors = m.bettors || [];
    const winner  = adminWinners[m.id] || null;

    const pickRows = bettors.map(name => {
      const pick = picks[name];
      let tag = '<span style="color:var(--text3);font-size:12px;">Not picked yet</span>';
      if (pick === 't1') tag = '<span class="pick-tag green">' + m.team1 + '</span>';
      if (pick === 't2') tag = '<span class="pick-tag green">' + m.team2 + '</span>';
      if (pick === 'none') tag = '<span class="pick-tag amber">Abstain</span>';
      return '<div class="pick-row" style="grid-template-columns:80px 1fr;">' +
             '<div class="pick-name">' + name + '</div>' + tag + '</div>';
    }).join('');

    const winBtns = [
      { val: 't1', label: m.team1 },
      { val: 't2', label: m.team2 },
    ].map(b =>
      '<button class="win-btn' + (winner === b.val ? ' selected' : '') + '" ' +
      'onclick="setAdminWinner(' + m.id + ', \'' + b.val + '\')">' + b.label + '</button>'
    ).join('');

    const isRevealed = !!m.teams_revealed;
    const revealBtnLabel = isRevealed ? '🙈 Hide Teams' : '👁 Reveal Teams';
    const revealBtnStyle = isRevealed
      ? 'background:var(--green-bg);color:var(--green);border:1px solid rgba(45,186,135,0.4);'
      : 'background:var(--surface2);color:var(--text2);border:1px solid var(--border);';

    return `
      <div class="card" style="margin-bottom:16px;" id="adminMatch-${m.id}">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;">
          <div>
            <div style="font-family:'Syne',sans-serif;font-size:17px;font-weight:700;color:var(--text);">
              ${m.team1} <span style="color:var(--text3)">vs</span> ${m.team2}
            </div>
            <div style="font-size:12px;color:var(--text3);">${fmtDate(m.match_date)}</div>
          </div>
          <div style="display:flex;gap:8px;align-items:center;">
            <button style="padding:6px 12px;border-radius:20px;font-size:12px;font-weight:600;cursor:pointer;transition:all 0.2s;${revealBtnStyle}"
              onclick="toggleRevealTeams(${m.id}, ${!isRevealed})">${revealBtnLabel}</button>
            <button class="del-btn" onclick="cancelActiveMatch(${m.id})">Cancel</button>
          </div>
        </div>

        <div class="pot-bar" style="margin-bottom:14px;">
          <span class="pot-text">🫙 Pot</span>
          <span class="pot-amount">₹${m.pot}</span>
          <span class="pot-text" style="font-size:12px;">${m.picked_count}/${m.total_bettors} picked</span>
        </div>

        <div class="pick-grid" style="margin-bottom:16px;">${pickRows}</div>

        <div style="border-top:1px solid var(--border);padding-top:14px;">
          <label class="field-label" style="margin-bottom:10px;">Actual winner</label>
          <div class="winner-row">${winBtns}</div>
          <div class="action-row" style="margin-top:14px;">
            <button class="btn-primary" onclick="finalizeMatch(${m.id})">Finalize &amp; Record</button>
          </div>
        </div>
      </div>`;
  }).join('');
}

function setAdminWinner(matchId, val) {
  adminWinners[matchId] = val;
  renderAdminMatchList();
}

function toggleMember(btn) { btn.classList.toggle('on'); }

function getActiveBettors() {
  return [...document.querySelectorAll('#memberToggles .toggle-btn.on')].map(b => b.dataset.name);
}

async function openNewMatch() {
  const t1      = document.getElementById('team1').value.trim();
  const t2      = document.getElementById('team2').value.trim();
  const date    = document.getElementById('matchDate').value;
  const bettors = getActiveBettors();
  if (!t1 || !t2)       return showAlert('Enter both team names.', 'error');
  if (!bettors.length)  return showAlert('Select at least one bettor.', 'error');

  try {
    const newMatch = await apiFetch('/api/active-matches', {
      method: 'POST',
      body: JSON.stringify({ team1: t1, team2: t2, match_date: date, bettors }),
    });
    activeMatches.push(newMatch);
    document.getElementById('team1').value = '';
    document.getElementById('team2').value = '';
    renderAdminMatchList();
    showAlert('Match opened: ' + t1 + ' vs ' + t2 + ' 🏏', 'success');
  } catch (e) { showAlert('Error: ' + e.message, 'error'); }
}

async function finalizeMatch(matchId) {
  const winner = adminWinners[matchId];
  if (!winner) return showAlert('Select the actual winner first.', 'error');

  try {
    const result = await apiFetch('/api/active-matches/' + matchId + '/finalize', {
      method: 'POST',
      body: JSON.stringify({ winner_team: winner }),
    });
    activeMatches = activeMatches.filter(m => m.id !== matchId);
    delete adminWinners[matchId];
    renderAdminMatchList();
    await loadStats();
    const wName   = result.winner_name;
    const winners = result.bettors.filter(m => result.picks[m] === result.winner_team);
    showAlert(
      wName !== '—'
        ? 'Recorded! ' + wName + ' won · ' + winners.join(' & ') + ' split ₹' + result.pot + ' 🎉'
        : 'Recorded — no winners this round.',
      'success'
    );
  } catch (e) { showAlert('Error: ' + e.message, 'error'); }
}

async function cancelActiveMatch(matchId) {
  if (!confirm('Cancel this match? Picks will be lost.')) return;
  try {
    await apiFetch('/api/active-matches/' + matchId, { method: 'DELETE' });
    activeMatches = activeMatches.filter(m => m.id !== matchId);
    delete adminWinners[matchId];
    renderAdminMatchList();
    showAlert('Match cancelled.', 'success');
  } catch (e) { showAlert('Error: ' + e.message, 'error'); }
}

async function toggleRevealTeams(matchId, reveal) {
  try {
    await apiFetch('/api/active-matches/' + matchId + '/reveal', {
      method: 'PATCH',
      body: JSON.stringify({ revealed: reveal }),
    });
    const m = activeMatches.find(x => x.id === matchId);
    if (m) m.teams_revealed = reveal;
    renderAdminMatchList();
    showAlert(reveal ? '👁 Teams revealed to all players.' : '🙈 Teams hidden from players.', 'success');
  } catch (e) { showAlert('Error: ' + e.message, 'error'); }
}

/* ══════════════════════════════════════════════════════════════════════════════
   HISTORY
══════════════════════════════════════════════════════════════════════════════ */
async function renderHistory() {
  const card = document.getElementById('historyCard');
  card.innerHTML = '<div class="empty"><span class="spinner"></span>Loading…</div>';
  let matches;
  try { matches = await apiFetch('/api/matches'); }
  catch (e) {
    card.innerHTML = '<div class="empty"><span class="empty-icon">⚠️</span>Failed: ' + e.message + '</div>';
    return;
  }
  if (!matches.length) {
    card.innerHTML = '<div class="empty"><span class="empty-icon">🏏</span>No matches yet</div>';
    return;
  }
  const totals = {};
  allMembers.forEach(m => totals[m] = 0);
  matches.slice().reverse().forEach(match => {
    match.bettors.forEach(m => { totals[m] = (totals[m] || 0) + match.payouts[m]; });
  });
  const isAdmin    = currentRole === 'admin';
  const memberCols = allMembers.map(m => '<th>' + m + '</th>').join('');
  const totalsRow  = allMembers.map(m => {
    const n   = Math.round(totals[m] || 0);
    const cls = n > 0 ? 'cell-won' : n < 0 ? 'cell-lost' : 'cell-neutral';
    return '<td class="' + cls + '">' + (n >= 0 ? '+' : '') + '₹' + Math.abs(n) + '</td>';
  }).join('');

  const rows = matches.map(match => {
    const dateStr = match.match_date
      ? new Date(match.match_date + 'T00:00:00').toLocaleDateString('en-IN', {day:'numeric',month:'short'})
      : '—';
    const matchLabel  = match.team1 + ' vs ' + match.team2;
    const winnerLabel = match.winner_name;
    const memberCells = allMembers.map(m => {
      if (!match.bettors.includes(m)) return '<td class="cell-neutral">—</td>';
      const n   = match.payouts[m];
      const cls = n > 0 ? 'cell-won' : n < 0 ? 'cell-lost' : 'cell-neutral';
      return '<td class="' + cls + '">' + fmtAmount(n) + '</td>';
    }).join('');
    const delCell = isAdmin
      ? '<td><button class="del-btn" onclick="deleteMatch(' + match.id + ')">✕</button></td>'
      : '<td></td>';
    return '<tr><td><div class="match-name">' + matchLabel + '</div>' +
           '<div class="match-date">' + dateStr + '</div>' +
           '<span class="winner-tag">' + winnerLabel + '</span></td>' +
           memberCells + delCell + '</tr>';
  }).join('');

  card.innerHTML =
    '<div class="table-wrap"><table>' +
    '<thead><tr><th>Match</th>' + memberCols + '<th></th></tr></thead>' +
    '<tbody>' + rows + '</tbody>' +
    '<tfoot><tr class="totals-row"><td>Season Total</td>' + totalsRow + '<td></td></tr></tfoot>' +
    '</table></div>';
}

/* ══════════════════════════════════════════════════════════════════════════════
   LEADERBOARD
══════════════════════════════════════════════════════════════════════════════ */
async function renderLeaderboard() {
  const lbCard = document.getElementById('lbCard');
  lbCard.innerHTML = '<div class="empty"><span class="spinner"></span>Loading…</div>';
  let stats;
  try { stats = await apiFetch('/api/stats'); }
  catch (e) {
    lbCard.innerHTML = '<div class="empty"><span class="empty-icon">⚠️</span>Failed: ' + e.message + '</div>';
    return;
  }
  const lb = stats.leaderboard;
  if (!lb || !lb.length || stats.total_matches === 0) {
    lbCard.innerHTML = '<div class="empty"><span class="empty-icon">🏆</span>No data yet</div>';
    return;
  }
  const maxAbs = Math.max(1, ...lb.map(x => Math.abs(x.net)));
  const medals = ['🥇', '🥈', '🥉', ''];
  const items  = lb.map((item, i) => {
    const pct    = Math.max(4, Math.round(Math.abs(item.net) / maxAbs * 100));
    const sign   = item.net >= 0 ? '+' : '';
    const amtCls = item.net > 0 ? 'pos' : item.net < 0 ? 'neg' : 'zero';
    const barCls = item.net < 0 ? 'neg' : '';
    return '<div class="lb-item' + (i === 0 ? ' first' : '') + '">' +
      '<div class="lb-rank' + (i === 0 ? ' gold' : '') + '">' + (medals[i] || (i+1)) + '</div>' +
      '<div class="lb-avatar">' + item.name.slice(0,2).toUpperCase() + '</div>' +
      '<div style="flex:1;"><div class="lb-name">' + item.name + '</div>' +
      '<div class="lb-games">' + item.games + ' match' + (item.games !== 1 ? 'es' : '') + '</div></div>' +
      '<div class="lb-bar-wrap"><div class="lb-bar ' + barCls + '" style="width:' + pct + '%"></div></div>' +
      '<div class="lb-amount ' + amtCls + '">' + sign + '₹' + Math.abs(item.net) + '</div></div>';
  }).join('');

  const summaryRows = lb.map(item => {
    const sign = item.net >= 0 ? '+' : '';
    const cls  = item.net > 0 ? 'cell-won' : item.net < 0 ? 'cell-lost' : 'cell-neutral';
    return '<tr><td><strong>' + item.name + '</strong></td><td>' + item.games + '</td>' +
           '<td class="cell-won">' + item.wins + '</td><td class="cell-lost">' + item.losses + '</td>' +
           '<td>' + (item.win_pct > 0 ? item.win_pct + '%' : '—') + '</td>' +
           '<td class="' + cls + '">' + sign + '₹' + Math.abs(item.net) + '</td></tr>';
  }).join('');

  lbCard.innerHTML =
    '<div class="lb-list" style="margin-bottom:20px;">' + items + '</div>' +
    '<div class="card"><div class="card-title">Season Stats</div>' +
    '<div class="table-wrap"><table><thead><tr>' +
    '<th>Name</th><th>Played</th><th>Wins</th><th>Losses</th><th>Win %</th><th>Net</th>' +
    '</tr></thead><tbody>' + summaryRows + '</tbody></table></div></div>';
}

/* ── Helpers ─────────────────────────────────────────────────────────────── */
function showAlert(msg, type) {
  const box = document.getElementById('alertBox');
  box.textContent = msg;
  box.className = 'alert ' + type;
  clearTimeout(box._timer);
  box._timer = setTimeout(() => { box.className = 'alert'; }, 5000);
}

function fmtAmount(n) {
  const abs = Math.abs(Math.round(n));
  return (n >= 0 ? '+' : '-') + '₹' + abs;
}

function fmtDate(d) {
  if (!d) return '—';
  return new Date(d + 'T00:00:00').toLocaleDateString('en-IN', {day:'numeric', month:'short', year:'numeric'});
}

async function deleteMatch(id) {
  if (currentRole !== 'admin') return showAlert('Admin access required.', 'error');
  if (!confirm('Delete this match?')) return;
  try {
    await apiFetch('/api/matches/' + id, { method: 'DELETE' });
    await loadStats();
    renderHistory();
  } catch (e) { showAlert('Delete failed: ' + e.message, 'error'); }
}

async function clearAll() {
  if (!confirm('Delete ALL match data? Cannot be undone.')) return;
  try {
    await apiFetch('/api/matches/clear', { method: 'DELETE' });
    showAlert('All data cleared.', 'success');
    await loadStats();
  } catch (e) { showAlert('Error: ' + e.message, 'error'); }
}

/* ── Auth / Login Modal ──────────────────────────────────────────────────── */
function openLoginModal() {
  document.getElementById('loginOverlay').classList.add('open');
  document.getElementById('adminPassword').value = '';
  const a = document.getElementById('loginAlert');
  a.textContent = ''; a.className = 'alert';
  setTimeout(() => document.getElementById('adminPassword').focus(), 100);
}

function closeLoginModal(e) {
  if (e && e.target !== document.getElementById('loginOverlay')) return;
  document.getElementById('loginOverlay').classList.remove('open');
}

async function submitLogin() {
  const pw  = document.getElementById('adminPassword').value;
  const btn = document.getElementById('loginBtn');
  if (!pw) return;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>Checking…';
  const alertEl = document.getElementById('loginAlert');
  alertEl.textContent = ''; alertEl.className = 'alert';

  try {
    await apiFetch('/api/login', { method: 'POST', body: JSON.stringify({ password: pw }) });
    currentRole = 'admin';
    await applyRoleUI();
    document.getElementById('loginOverlay').classList.remove('open');
    showAlert('Logged in as admin ⚡', 'success');
  } catch (e) {
    alertEl.textContent = e.message || 'Invalid password';
    alertEl.className   = 'alert error';
  } finally {
    btn.disabled = false;
    btn.innerHTML = 'Login';
  }
}

async function doLogout() {
  try { await apiFetch('/api/logout', { method: 'POST' }); } catch (_) {}
  currentRole   = 'guest';
  myName        = null;
  selectedMatch = null;
  activeMatches = [];
  adminWinners  = {};
  await applyRoleUI();
  showAlert('Logged out.', 'success');
}
