# Love Live Event Design Plan

**Updated:** 2026-09-23  
**Status:** Design proposal responding to the user's color feedback; ready for implementation planning.  
**Related requirements:** [Bracket feature plan](BRACKET_FEATURE_PLAN.md)

## Direction and reference

Replace the current blue/green scheme with a bright festival palette inspired by the supplied Love Live anniversary artwork: white space, warm brown outlines, vivid pink, strawberry coral, golden yellow, and small orange and violet accents. The intended feel is cheerful, warm, and celebratory, with the bracket and results remaining the visual focus.

The image is a color and visual reference. Its anniversary wording, logo, cake, and other artwork do not become required interface content. The colors below are proposed UI equivalents inspired by the image, not an official brand palette or exact pixel samples.

[Saved reference image](references/love-live-fest-color-reference.png)

This plan changes visual presentation across the public projector display, attendee voting interface, and owner/admin controls. All functionality in the feature plan remains in scope. The Love Live songs toggle continues to control song matching; this design does not introduce a theme toggle or additional voting behavior.

## Palette and roles

| Role | Proposed color | Use |
| --- | --- | --- |
| Page background | Warm white `#FFFAF6` | Main canvas; almost white so the screen remains bright and clear. |
| Card surface | White `#FFFFFF` | Bracket entries, result panels, inputs, and QR panel. |
| Main text | Dark cocoa `#3D281F` | Song names, vote counts, labels, and body text. |
| Structure | Warm brown `#70503C` | Headings, bracket connectors, card borders, and strong outlines inspired by the artwork. |
| Primary accent | Festival pink `#FF4DB8` | Active matchup accents, small highlights, and decorative bands. |
| Action color | Deep berry `#A82069` | Filled primary buttons and selected voting choices, with white text. A darker UI companion to the artwork's pink. |
| Secondary accent | Strawberry coral `#FF5268` | Small festive accents and emphasis outside voting status indicators. |
| Winner accent | Golden yellow `#FFCB35` | Winner highlight, final result emphasis, and small celebratory details. |
| Supporting accent | Tangerine `#FF983E` | Limited decoration in headers or accent strips. |
| Supporting accent | Violet `#BA5FF1` | Limited decoration in headers or accent strips. |
| Active background | Pale pink `#FFF0F8` | Background behind the current matchup or an active control group. |
| Winner background | Pale gold `#FFF4CE` | Revealed winning entry and final result surfaces. |
| Quiet background | Warm neutral `#F3EAE3` | Waiting/closed status surfaces and inactive controls. |
| QR modules | Black `#000000` on white | The scannable QR graphic, with clear surrounding white space. |

Use white and warm white for most of the screen, cocoa/brown for structure, and pink as the main accent. Gold identifies a revealed winner. Coral, orange, and violet should occupy small areas so a dense bracket does not become a rainbow of competing highlights. Blue and green are removed from the core visual scheme.

Bright accent fills should use dark cocoa text where contrast permits. White text belongs on deep berry, not on yellow or other bright accents. Violet is decorative rather than a background for small text. Implementation should check the actual foreground/background pairs against the contrast targets below.

## Public projector display

Keep the existing display purpose and bracket progression. Use the new palette to make the event feel cohesive while preserving clear hierarchy:

1. The bracket and entry names occupy the main space on a warm white canvas.
2. The current matchup is identified by a pink border, pale pink surface, and an explicit voting-state label. Emphasize the matchup as a whole so both competing entries have equal visual weight before the result.
3. Revealed results use pale gold, a strong brown outline, and a winner label. Vote counts remain dark cocoa and prominent beside each participating entry when public voting is enabled.
4. The QR code sits in a stable, reserved white panel with a brown frame and a short dark label such as “Scan to vote.” It stays visible for as long as public voting is enabled, including closed voting and result transitions.

For 32 and 64 entries, retain the two-sided bracket converging toward the central final. Both sides use the same colors and styling. Do not assign a different theme color to each side or entry: state highlights must remain easy to identify.

Use brown connectors with sufficient thickness to survive projection. A winner's advancing path may receive a gold accent while retaining a brown outline or underlying line. Yellow alone must not carry essential bracket structure against white.

Keep decorations out of entry cards, connector paths, and the QR code's white margin. Give long song names readable space; decorative headers and borders must not force smaller bracket text. Do not fade eliminated entries to low contrast—the audience still needs to read names and results.

## Voting and result states

| Existing state | Visual treatment |
| --- | --- |
| Waiting for voting / closed before reveal | White or warm neutral surface, cocoa text, brown outline, explicit state label. No winner styling. |
| Voting open | Pale pink matchup surface and strong pink border, with “Voting open” in dark text. Both candidates retain equal emphasis on the public display. |
| Attendee's selected choice | Deep berry border or fill and an explicit selection marker/label. This indicates the attendee's choice, not the event winner. |
| Winner revealed | Pale gold surface, brown outline, a gold accent, winner label, and dark vote counts for both participants when public voting is enabled. |
| Final winner | The same winner treatment, with stronger visual emphasis at the bracket's center. |

State must be understandable from labels and structure as well as color. Avoid treating every positive state as green or using coral decoration as an error signal. Existing errors should use a distinct dark red and clear text.

This plan styles revealed vote counts; it does not decide whether running totals appear while voting is open. That remains an open product decision in the feature plan.

## Attendee and owner/admin surfaces

Apply the same white/cocoa/pink palette so scanning the QR code leads to a visually consistent voting experience. Use deep berry with white text for existing primary actions and brown outlines with dark text for secondary actions. Preserve the existing action labels and voting sequence.

Owner/admin forms use white fields, readable cocoa labels, and clear brown borders. Existing toggles can use deep berry for the enabled state and warm neutral for disabled, with position and text making their state clear. Provide a visible focus outline that remains distinct from selected-choice styling.

Use a friendly, rounded heading style with strong weight. Keep song names, controls, and numeric results in a highly readable font with suitable Japanese character support. Avoid decorative outlined lettering for bracket data. Vote counts should use consistently aligned digits where supported. Existing suitable fonts can be retained; a font change is not required for this palette update.

## Implementation handoff

1. Identify the existing shared theme values and component-specific blue/green styling. Map them to the roles in this plan rather than replacing every blue/green value with the same pink.
2. Apply the neutral canvas, text, borders, and action colors across all existing surfaces.
3. Apply the active-matchup and winner treatments, keeping those two states distinct and avoiding any visual indication of a winner before reveal.
4. Apply the projector layout styling while preserving the central bracket arrangement, vote counts, and permanent QR space.
5. Review the public display, voting interface, and owner controls together for inconsistent old-theme colors and weak contrast.

These steps describe implementation work for another agent. No application code is introduced by this plan.

## Design acceptance criteria

- The overall impression follows the reference: white, warm brown, pink, and gold, with restrained supporting accents.
- The blue/green scheme no longer defines page backgrounds, cards, actions, connectors, or voting states.
- The public display continues to show data and progress; creation and administration remain in the owner/admin area.
- The 32-entry and 64-entry layouts remain balanced across both sides and converge to the center.
- The QR code remains fully visible while public voting is enabled, with black modules, white background, unobstructed white margin, and no decorative overlays.
- Open voting, attendee selection, and revealed winners have distinct styling and explicit labels.
- Revealed results show readable vote counts for both entries when public voting is enabled, including the losing entry.
- Target at least 4.5:1 contrast for ordinary text and 3:1 for essential connectors, control boundaries, and focus indicators against adjacent backgrounds. Verify final colors rather than assuming every palette combination works.
- Review the proposed styling at the intended projector resolution with both 32 and 64 entries, long song names, and revealed vote totals. Projection readability takes priority over decorative styling.
- Existing song links, manual YouTube ID fallback, and voting controls remain available according to the feature plan.

## Optional embellishments for later feedback

A small strip using the reference's pink, coral, gold, orange, and violet, or a few static star shapes near the title, could reinforce the festival feel. These are optional proposals; they should not occupy bracket or QR space. The core design works with the palette, typography, borders, and state treatments alone.
