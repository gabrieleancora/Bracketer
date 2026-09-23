# Bracket Website Feature Plan

**Status:** Draft for product review  
**Last updated:** 2026-09-23 — projector display, voting QR visibility, bracket layout, and result vote counts.  
**Purpose:** Record the requested product behavior for implementation agents. This document defines the requested baseline and separates unresolved decisions and optional proposals from it.

**Visual design:** See the [Love Live event design plan](DESIGN_PLAN.md) for the requested replacement of the blue/green scheme, the reference image, proposed palette, component treatments, and design acceptance criteria. This feature plan remains the source for product behavior.

## Product goal

Build a simple website where an owner can create a bracket, enter names, save it, and publish it through owner/admin controls. The public site is a display of the published bracket, intended for projection so attendees can follow voting and results in real time. It does not offer bracket creation or administration. The bracket owner controls winners directly unless public voting is enabled. With public voting enabled, attendees scan the displayed QR code to access voting without registering.

## Access and display responsibilities

| Surface | Purpose and available actions |
| --- | --- |
| Owner/admin area | Create and save brackets, enter data, configure settings, publish, update winners when public voting is disabled, and manage the voting sequence when enabled. |
| Public bracket display | Show bracket data, voting progress, revealed results, and the voting QR code when enabled. Intended for a projector; no bracket creation, editing, winner selection, or voting administration controls. |
| Attendee voting interface reached through the QR code | Allow anonymous attendees to vote on the currently open matchup from their own devices. No bracket creation or administration. |

These are functional responsibilities; the plan does not require separate applications or select a routing architecture. Anonymous voting remains available through the QR code while the projected bracket serves as the public display.

## Requested baseline

### Create and save a bracket

- Through the owner/admin area, a user can create a bracket and enter the name for each entry.
- Through the owner/admin area, a user can save the bracket and return to its saved state.
- After saving, the owner can enable the **Public voting** toggle.
- Bracket setup includes a **Love Live songs** toggle.
- The bracket can be published. Public access and the owner controls follow the rules below.

### Published bracket with public voting disabled

- Only the bracket owner can update winners.
- Public visitors can view the published bracket.

### Published bracket with public voting enabled

- Attendees can access the voting interface through a QR code displayed on the public bracket page.
- The QR code is always visible while public voting is enabled, including before voting opens, while voting is open, after voting closes, during result display, and between matchups. Visibility depends on the public voting setting, not on whether a vote is currently open.
- Keep the QR code visible in the projector viewport without scrolling or opening a menu, and without bracket content or results covering it.
- Visitors can vote without creating or registering for an account.
- Only one vote/matchup is open at a time.
- The admin can open voting, close voting, show the winner, and proceed to the next vote.
- The public page updates in real time so visitors can follow the bracket's progress.
- Revealed matchup results show the winner and the number of votes received by each participating entry. This applies when public voting is enabled; displaying a running tally before the reveal remains an open decision.

### Projector display and bracket layout

- Design the public bracket page for an audience following the event on a projector: entry names, bracket progression, revealed results, vote counts, and the QR code must remain readable in the intended projection layout.
- Brackets converge toward the center, with the final matchup/result at the center.
- For 32 entries, display the bracket on both sides, with 16 starting entries on each side and rounds progressing inward toward the center.
- For 64 entries, display the bracket on both sides, with 32 starting entries on each side and rounds progressing inward toward the center.
- Reserve visible space for the QR code whenever public voting is enabled so the bracket and result layout do not hide it.
- The centered visual arrangement does not select a tournament format or seeding rule; those remain decisions below.

### Love Live song links

- When the Love Live songs option is enabled, match each entry name against the supplied song data:
  [song-info.json](https://raw.githubusercontent.com/hamproductions/the-sorter/refs/heads/main/data/song-info.json)
- Use the matched record's `videoId` to show a YouTube link with the entry name for quick listening.
- If no match is found, let the user enter a YouTube ID manually.
- When the option is disabled, do not apply Love Live matching.

## Core user flows

1. The owner creates a bracket, adds entry names, optionally enables Love Live songs, and saves it.
2. After saving, the owner can configure public voting and publish the bracket; the relationship between those actions is a decision listed below.
3. With voting disabled, the owner advances winners manually.
4. With voting enabled, the projector shows the public bracket with its QR code continuously visible. Attendees scan the code and vote on their own devices while the current vote is open. The admin closes voting, reveals the winner and entry vote counts, and proceeds to the next vote. The projected bracket updates live throughout this sequence.
5. With Love Live songs enabled, a matched entry gets its YouTube link from `videoId`; an unmatched entry can be given a YouTube ID manually.

## Acceptance criteria for the requested baseline

- A bracket and its entry names can be saved and later displayed.
- Bracket creation and management are available through the owner/admin area. The public display and attendee voting interface do not expose those actions.
- The owner can enable public voting on a saved bracket.
- A published bracket with public voting disabled allows winner updates by its owner only.
- A published bracket with public voting enabled has a QR code that leads attendees to voting without registration. The QR code remains visible in the projector viewport throughout open voting, closed voting, result reveals, and transitions between matchups, without scrolling or opening controls.
- The admin can control the open/closed state of the current vote, reveal its winner, and advance to the next vote; there is never more than one open vote at a time.
- Public viewers see bracket progress updates without manually reloading the page.
- Brackets progress toward a central final matchup/result. A 32-entry bracket starts with 16 entries on each side; a 64-entry bracket starts with 32 entries on each side. Both sides converge inward.
- When public voting is enabled, revealed matchup results include the winner and numeric vote counts for each participating entry, visible on the public display.
- The projector layout keeps the bracket, revealed results, and enabled QR code readable without overlap.
- With Love Live songs enabled, matched entries use the dataset's `videoId` for a YouTube link; unmatched entries accept a manually supplied YouTube ID.

## Decisions needed before implementation

These details are not specified in the request and should not be silently fixed by implementation:

1. **Save and publication:** Is saving separate from publishing, or does saving make a bracket public? Can a published bracket be unpublished?
2. **Bracket format:** What progression format is intended, and how should entry counts, byes, and matchup ordering work? The centered layout and two-sided arrangement for 32/64 entries are confirmed requirements, independent of these choices.
3. **Owner/admin identity:** Is the admin always the bracket owner, and what sign-in or ownership mechanism should protect owner controls?
4. **Anonymous vote policy:** Does “one vote at a time” mean one active matchup, as captured above, or should each attendee also be limited to one ballot per matchup? With anonymous access, repeat-vote expectations need to be explicit.
5. **Vote outcome:** How should a tie or a closed vote with no ballots be handled before showing a winner?
6. **Live visibility:** Should visitors also see the running tally while voting is open? Showing the winner and vote counts when the admin reveals results is required; visibility before that reveal is undecided.
7. **Song matching:** Should matching be exact, case-insensitive/normalized, or use another rule? What should happen if more than one record matches?
8. **Manual YouTube ID scope:** Is manual entry needed only when no song match exists, or should owners also be able to replace a matched ID?

## Optional proposals for review

These are not part of the requested baseline unless approved:

- Let the owner choose a candidate when a song name matches multiple records.
- Add a repeat-vote policy for anonymous attendees, such as limiting a browser/session to one ballot per matchup. This cannot reliably establish a unique person without registration.
- Define and display a tie/no-vote resolution rule so every closed vote can advance.
- Let the owner correct a matched YouTube ID in addition to supplying one for unmatched songs.

## Scope boundaries

- The public site displays bracket data for projection. Bracket creation and administration belong to the owner/admin area; attendees access anonymous voting through the QR code.
- Public voters do not need accounts.
- No specific web framework, realtime transport, storage technology, authentication provider, or QR-code library is selected by this plan.
- No playback player behavior is specified; the requested baseline is a YouTube link associated with the entry.
- Do not add voting modes, bracket formats, song catalogs, or administrative roles until clarified or approved.
