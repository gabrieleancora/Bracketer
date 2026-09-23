const config = window.BRACKET;
const base = `/api/owner/${config.id}/${config.token}`;
let state = null;
let currentVersion = 0;

function el(tag, className, content) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (content !== undefined) node.textContent = content;
  return node;
}

function entry(id) { return state.entries[id]; }
function matchById(id) { return state.rounds.flat().find(match => match.id === id); }
function nameFor(id) { return id === null ? 'To be decided' : entry(id).name; }

async function send(url, payload) {
  const response = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Something went wrong.');
  await load(true);
}

async function act(url, payload) {
  try { await send(url, payload); showNotice(''); }
  catch (error) { showNotice(error.message); }
}

function showNotice(message, success=false) {
  const notice = document.getElementById('notice');
  notice.textContent = message; notice.hidden = !message; notice.classList.toggle('success', success);
}

function button(label, callback, className='small-button') {
  const node = el('button', className, label); node.type = 'button'; node.addEventListener('click', callback); return node;
}

function songLink(id) {
  const item = entry(id);
  if (!item.video_id) return null;
  const link = el('a', 'song-link', '↗ Listen');
  link.href = `https://www.youtube.com/watch?v=${encodeURIComponent(item.video_id)}`;
  link.target = '_blank'; link.rel = 'noopener noreferrer';
  return link;
}

function drawRounds() {
  const rounds = document.getElementById('rounds'); rounds.replaceChildren();
  document.getElementById('round-count').textContent = `${state.rounds.length} ROUND${state.rounds.length === 1 ? '' : 'S'} · ${state.entries.length} ENTRIES`;
  state.rounds.forEach((matches, roundIndex) => {
    const column = el('div', 'round');
    const heading = el('div', 'round-heading', roundIndex === state.rounds.length - 1 ? 'FINAL' : `ROUND ${String(roundIndex + 1).padStart(2, '0')}`);
    column.append(heading);
    matches.forEach((match, index) => {
      const card = el('div', 'match');
      const label = el('div', 'match-label', `MATCH ${String(index + 1).padStart(2, '0')}`);
      if (state.voting.current === match.id && state.public_voting) label.append(el('span', 'match-state', state.voting.phase.toUpperCase()));
      card.append(label);
      [match.a, match.b].forEach(id => {
        const row = el('div', `contestant${match.winner === id && id !== null ? ' winner' : ''}${id === null ? ' pending' : ''}`);
        row.append(el('span', 'contestant-name', nameFor(id)));
        if (id !== null) {
          const link = songLink(id); if (link) row.append(link);
          if (!state.public_voting) row.append(button(match.winner === id ? '✓' : 'Pick', () => act(`${base}/winner`, {match_id:match.id, choice:id}), 'pick-button'));
        }
        card.append(row);
      });
      column.append(card);
    });
    rounds.append(column);
  });
}

function drawOwner() {
  const tools = document.getElementById('owner-tools'); tools.hidden = false;
  const published = document.getElementById('published'); published.checked = state.published;
  const publicVoting = document.getElementById('public-voting'); publicVoting.checked = state.public_voting;
  publicVoting.disabled = state.rounds.flat().some(match => match.winner !== null) || state.voting.phase !== 'idle';
  const share = document.getElementById('share'); share.hidden = !state.published;
  if (state.published) {
    const url = new URL(`/b/${config.id}`, location.href).href;
    const link = document.getElementById('public-link'); link.href = url; link.textContent = url;
  }
  const controls = document.getElementById('vote-controls'); controls.hidden = !state.public_voting; controls.replaceChildren();
  if (state.public_voting) {
    const current = matchById(state.voting.current);
    const header = el('div', 'controls-heading'); header.append(el('span', 'step', 'PUBLIC VOTE'), el('h3', '', current ? `${nameFor(current.a)} vs ${nameFor(current.b)}` : 'Next matchup'));
    controls.append(header);
    const phase = state.voting.phase;
    controls.dataset.phase = phase;
    if (phase === 'idle') {
      const next = current || state.rounds.flat().find(match => match.a !== null && match.b !== null && match.winner === null);
      controls.append(next ? button('Open voting →', () => act(`${base}/vote-control`, {action:'open'}), 'primary-button') : el('p', 'muted', 'The bracket is complete.'));
    } else if (phase === 'open') {
      controls.append(el('p', 'muted', 'Voting is open. Attendees can scan the QR code on the projector display.'));
      controls.append(button('Close voting', () => act(`${base}/vote-control`, {action:'close'}), 'primary-button'));
    } else if (phase === 'closed' && current) {
      const a = Number(state.counts?.[current.a] || 0), b = Number(state.counts?.[current.b] || 0);
      controls.append(el('p', 'score', `${nameFor(current.a)} ${a}  ·  ${b} ${nameFor(current.b)}`));
      if (a === b) {
        controls.append(el('p', 'muted', 'The vote is tied or has no ballots. Choose a winner to reveal.'));
        [current.a, current.b].forEach(id => controls.append(button(`Reveal ${nameFor(id)}`, () => act(`${base}/vote-control`, {action:'reveal', choice:id}))));
      } else controls.append(button('Reveal winner', () => act(`${base}/vote-control`, {action:'reveal'}), 'primary-button'));
    } else if (phase === 'revealed' && current) {
      controls.append(el('p', 'score', `Winner: ${nameFor(current.winner)}`));
      controls.append(button('Proceed to next vote →', () => act(`${base}/vote-control`, {action:'advance'}), 'primary-button'));
    }
  }
  const songs = document.getElementById('song-controls'); songs.replaceChildren();
  const unmatched = state.love_live ? state.entries.filter(item => !item.matched) : [];
  songs.hidden = unmatched.length === 0;
  if (unmatched.length) {
    songs.append(el('span', 'step', 'SONG LINKS'), el('h3', '', 'Add missing YouTube IDs'));
    unmatched.forEach(item => {
      const row = el('form', 'video-row');
      const label = el('label', '', item.name); label.htmlFor = `video-${item.id}`;
      const input = el('input'); input.id = `video-${item.id}`; input.placeholder = 'YouTube video ID'; input.value = item.video_id || ''; input.maxLength = 11;
      row.append(label, input, button('Save', () => act(`${base}/entries/${item.id}/video`, {video_id:input.value})));
      row.addEventListener('submit', event => { event.preventDefault(); act(`${base}/entries/${item.id}/video`, {video_id:input.value}); });
      songs.append(row);
    });
  }
}

function drawVote() {
  const panel = document.getElementById('live-vote'); panel.replaceChildren(); panel.hidden = true;
  if (!state.public_voting || !state.published) return;
  const current = matchById(state.voting.current);
  if (!current) return;
  panel.hidden = false;
  panel.append(el('span', 'step', 'CURRENT MATCHUP'));
  panel.append(el('h2', '', `${nameFor(current.a)} vs ${nameFor(current.b)}`));
  const phase = state.voting.phase;
  panel.dataset.phase = phase;
  if (phase === 'open') {
    panel.append(el('p', 'muted', 'Voting is open on the attendee page.'));
  } else if (phase === 'closed') panel.append(el('p', 'muted', 'Voting is closed. Waiting for the winner to be revealed.'));
  else if (phase === 'revealed') panel.append(el('p', 'revealed-winner', `Winner · ${nameFor(current.winner)}`));
  else panel.append(el('p', 'muted', 'The next vote will open soon.'));
}

function render() {
  document.title = `${state.title} · Bracketer`;
  document.getElementById('title').textContent = state.title;
  document.getElementById('status').textContent = state.published ? (state.public_voting ? 'LIVE BRACKET · PUBLIC VOTING' : 'PUBLISHED BRACKET') : 'PRIVATE DRAFT';
  document.getElementById('subtitle').textContent = 'Choose winners, configure voting, and share the bracket when you are ready.';
  drawRounds(); drawVote(); drawOwner();
}

async function load(force=false) {
  const response = await fetch(base);
  if (!response.ok) {
    showNotice('Could not load the bracket.'); return;
  }
  const next = await response.json();
  if (force || next.version !== currentVersion || next.has_voted !== state?.has_voted) { state = next; currentVersion = next.version; render(); }
}

document.getElementById('published').addEventListener('change', event => act(`${base}/settings`, {field:'published', value:event.target.checked}));
document.getElementById('public-voting').addEventListener('change', event => act(`${base}/settings`, {field:'public_voting', value:event.target.checked}));
document.getElementById('copy-owner').addEventListener('click', async () => {
  try { await navigator.clipboard.writeText(location.href); showNotice('Owner link copied.', true); }
  catch { showNotice('Copy the owner link from your browser address bar.'); }
});
load();
