const bracketId = window.BRACKET.id;
const endpoint = `/api/brackets/${bracketId}`;
let state = null;
let version = 0;

function node(tag, className, value) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (value !== undefined) element.textContent = value;
  return element;
}

function nameFor(id) { return id === null ? 'Awaiting winner' : state.entries[id].name; }
function votes(count) { return `${count} ${count === 1 ? 'vote' : 'votes'}`; }
function currentMatch() { return state.rounds.flat().find(match => match.id === state.voting.current); }
function nextReadyMatch() { return state.rounds.flat().find(match => match.a !== null && match.b !== null && match.winner === null); }

function matchCard(match) {
  const card = node('div', 'display-match');
  card.dataset.matchId = match.id;
  if (match.id === state.voting.current && state.voting.phase !== 'idle') card.classList.add('current');
  if (match.winner !== null) card.classList.add('decided');
  for (const id of [match.a, match.b]) {
    const row = node('div', 'display-entry');
    if (id === null) row.classList.add('pending');
    if (match.winner === id && id !== null) row.classList.add('winner');
    if (match.winner === id && id !== null) row.append(node('span', 'display-winner-mark', 'WINNER'));
    const name = node('span', 'display-entry-name', nameFor(id));
    name.title = nameFor(id);
    row.append(name);
    if (id !== null && state.results?.[match.id]) {
      row.append(node('span', 'display-entry-count', String(state.results[match.id][id] ?? 0)));
    }
    card.append(row);
  }
  return card;
}

function column(matches, roundIndex, side) {
  const section = node('div', `display-column ${side}`);
  section.dataset.round = String(roundIndex);
  section.append(node('div', 'display-column-heading', side === 'center' ? 'FINAL' : `ROUND ${roundIndex + 1}`));
  const lane = node('div', 'display-column-matches');
  lane.style.gridTemplateRows = `repeat(${matches.length}, minmax(0, 1fr))`;
  matches.forEach(match => {
    const slot = node('div', 'display-match-slot');
    if (match.winner !== null) slot.classList.add('decided');
    slot.append(matchCard(match));
    lane.append(slot);
  });
  section.append(lane);
  return section;
}

function renderTree() {
  const target = document.getElementById('display-rounds');
  target.replaceChildren();
  const last = state.rounds.length - 1;
  const sides = [];
  for (let round = 0; round < last; round++) {
    const matches = state.rounds[round];
    const half = matches.length / 2;
    sides.push({round, left: matches.slice(0, half), right: matches.slice(half)});
  }
  sides.forEach(part => target.append(column(part.left, part.round, 'left')));
  target.append(column(state.rounds[last], last, 'center'));
  sides.reverse().forEach(part => target.append(column(part.right, part.round, 'right')));
  target.style.gridTemplateColumns = `repeat(${target.children.length}, minmax(0, 1fr))`;
  target.style.setProperty('--outer-matches', String(state.rounds[0].length / 2 || 1));
  document.getElementById('round-count').textContent = `${state.entries.length} ENTRIES · ${state.rounds.length} ROUNDS`;
}

function renderFocus() {
  const target = document.getElementById('display-focus');
  target.replaceChildren();
  target.dataset.phase = state.public_voting ? state.voting.phase : 'manual';
  const match = currentMatch() || nextReadyMatch();
  const phase = state.voting.phase;
  const final = state.rounds.at(-1)[0];
  let label = 'BRACKET PROGRESS';
  let headline = final.winner !== null ? `Champion · ${nameFor(final.winner)}` : 'Awaiting the next result';
  let detail = '';
  if (state.public_voting && match) {
    if (phase === 'open') { label = 'VOTING OPEN'; headline = `${nameFor(match.a)}  vs  ${nameFor(match.b)}`; detail = 'Scan the QR code to vote'; }
    else if (phase === 'closed') { label = 'VOTING CLOSED'; headline = `${nameFor(match.a)}  vs  ${nameFor(match.b)}`; detail = 'Results coming soon'; }
    else if (phase === 'revealed') {
      label = 'RESULT REVEALED'; headline = `Winner · ${nameFor(match.winner)}`;
      const counts = state.results?.[match.id];
      if (counts) detail = `${nameFor(match.a)} ${votes(counts[match.a])}  ·  ${nameFor(match.b)} ${votes(counts[match.b])}`;
    } else { label = 'NEXT MATCHUP'; headline = `${nameFor(match.a)}  vs  ${nameFor(match.b)}`; detail = 'Waiting for voting to open'; }
  }
  const text = node('div', 'display-focus-text');
  text.append(node('span', 'step', label), node('h2', '', headline));
  if (detail) text.append(node('p', '', detail));
  target.append(text);
}

function render() {
  document.title = `${state.title} · Bracketer display`;
  document.getElementById('title').textContent = state.title;
  document.getElementById('status').textContent = state.public_voting ? 'PUBLIC VOTING' : 'OWNER RESULTS';
  const qr = document.getElementById('display-qr');
  qr.hidden = !state.public_voting;
  document.getElementById('display-page').classList.toggle('with-qr', state.public_voting);
  if (state.public_voting) document.getElementById('qr').src = `${endpoint}/qr.svg`;
  renderFocus(); renderTree();
}

async function load() {
  const response = await fetch(endpoint);
  if (!response.ok) {
    document.getElementById('notice').textContent = response.status === 404 ? 'This bracket is no longer published.' : 'Could not load the bracket.';
    return;
  }
  const next = await response.json();
  if (next.version !== version) { state = next; version = next.version; render(); }
}

const events = new EventSource(`${endpoint}/events`);
events.onmessage = load;
events.addEventListener('unpublished', () => { events.close(); document.getElementById('notice').textContent = 'This bracket is no longer published.'; });
load();
