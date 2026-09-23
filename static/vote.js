const bracketId = window.BRACKET_ID;
const endpoint = `/api/brackets/${bracketId}`;
let state = null;
let version = 0;

function element(tag, className, value) {
  const result = document.createElement(tag);
  if (className) result.className = className;
  if (value !== undefined) result.textContent = value;
  return result;
}

function nameFor(id) { return state.entries[id].name; }
function votes(count) { return `${count} ${count === 1 ? 'vote' : 'votes'}`; }

function render() {
  document.title = `Vote · ${state.title}`;
  document.getElementById('title').textContent = state.title;
  const content = document.getElementById('vote-content'); content.replaceChildren();
  const match = state.rounds.flat().find(item => item.id === state.voting.current);
  if (!match || state.voting.phase === 'idle') {
    content.append(element('p', 'attendee-message', 'Waiting for the next vote to open. This page will update automatically.'));
    return;
  }
  content.append(element('p', 'attendee-match', `${nameFor(match.a)} vs ${nameFor(match.b)}`));
  if (state.voting.phase === 'open') {
    if (state.has_voted) content.append(element('p', 'attendee-message', 'Your vote is recorded. Waiting for the result.'));
    else {
      content.append(element('p', 'attendee-message', 'Choose your favorite:'));
      const choices = element('div', 'attendee-options');
      for (const id of [match.a, match.b]) {
        const button = element('button', 'attendee-option', nameFor(id));
        button.addEventListener('click', () => vote(id));
        choices.append(button);
      }
      content.append(choices);
    }
  } else if (state.voting.phase === 'closed') content.append(element('p', 'attendee-message', 'Voting is closed. The owner will reveal the result soon.'));
  else {
    content.append(element('p', 'attendee-winner', `Winner · ${nameFor(match.winner)}`));
    const counts = state.results?.[match.id];
    if (counts) content.append(element('p', 'attendee-message', `${nameFor(match.a)} ${votes(counts[match.a])} · ${nameFor(match.b)} ${votes(counts[match.b])}`));
  }
}

async function load(force=false) {
  const response = await fetch(endpoint);
  if (!response.ok) {
    document.getElementById('notice').textContent = 'This vote is no longer available.';
    return;
  }
  const next = await response.json();
  if (force || next.version !== version || next.has_voted !== state?.has_voted) {
    if (next.version !== version) document.getElementById('notice').textContent = '';
    state = next; version = next.version; render();
  }
}

async function vote(choice) {
  const notice = document.getElementById('notice');
  notice.textContent = '';
  const buttons = document.querySelectorAll('.attendee-option');
  buttons.forEach(button => button.disabled = true);
  try {
    const response = await fetch(`${endpoint}/vote`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({choice})});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Could not record your vote.');
    await load(true);
    notice.textContent = 'Vote recorded.';
  } catch (error) {
    notice.textContent = error.message;
    buttons.forEach(button => button.disabled = false);
  }
}

const events = new EventSource(`${endpoint}/events`);
events.onmessage = load;
events.addEventListener('unpublished', () => { events.close(); document.getElementById('notice').textContent = 'This vote is no longer available.'; });
load();
