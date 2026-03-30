# CLAUDE.md - Panini Album Project Guide

> **IMPORTANT**: Read this file before making ANY changes to understand the architecture and avoid breaking existing features.

## Project Overview

Flask web application for collecting FIFA World Cup 2026 Panini stickers. Users can:
- Track owned stickers and duplicates
- View other collectors and find trading partners
- Send trade messages to other users

## Architecture

### Backend (Python/Flask)

```
album/__init__.py     - App factory, database config, extensions
album/routes.py       - Main album routes (index, stats, exports)
album/auth.py         - Authentication, messages, trades
album/models.py       - SQLAlchemy models (User, Message, Trade, etc)
album/config.py       - Team/sticker configuration
```

### Frontend (Jinja2 Templates + Vanilla JS)

```
album/templates/
  base.html           - Layout with navbar, logout
  album.html          - Main album page with stickers
  auth/
    users.html        - Other collectors page (COMPLEX - see warnings below)
    messages.html     - Message inbox
    profile.html      - User profile
    login.html        - Login form
    register.html     - Registration form
```

## Critical Implementation Details

### JavaScript Scope Pattern

**WARNING**: This project uses inline `onclick` handlers in HTML. Functions MUST be exposed to global scope:

```javascript
// ❌ WRONG - IIFE hides functions
(function() {
  function openTradeModal() { ... }
})();

// ✅ CORRECT - Expose to window
(function() {
  function openTradeModal() { ... }
  window.openTradeModal = openTradeModal;
})();
```

### API Field Names

Backend expects specific field names. **Never change these without updating BOTH sides**:

```python
# Backend (album/auth.py)
recipient_username = data.get("recipient_username")  # NOT "recipient"
stickers = data.get("stickers", [])                   # NOT "sticker_ids"
content = data.get("content")
```

```javascript
// Frontend (users.html)
body: JSON.stringify({
  recipient_username: currentTradeData.username,  // CORRECT
  stickers: Array.from(currentTradeData.selectedStickers),  // CORRECT
  content: message
})
```

### CSS Naming Conventions

**NEVER modify existing CSS classes** - always create new ones:

```css
/* ❌ WRONG - breaks album page stickers */
.sticker-checkbox { ... }

/* ✅ CORRECT - unique to trade modal */
.trade-modal .sticker-checkbox { ... }
/* OR */
.sticker-select-item .sticker-checkbox { ... }
```

## File-Specific Warnings

### album/templates/auth/users.html

**MOST COMPLEX FILE** - Handle with extreme care.

1. **JavaScript at top**: Script block must be at line ~7, before HTML with onclick handlers
2. **Three interconnected features**:
   - Search filtering (by username or sticker ID with partial matching, e.g., "bra" matches "brazil" or "bra-17")
   - Card expansion (click trader card → show modal)
   - Trade modal (click "You Can Get/Give" → select stickers → send message)

3. **Element IDs that MUST exist**:
   - `userCardModal` - Modal for expanded trader cards
   - `modalCardContainer` - Container for cloned card
   - `tradeModal` - Trade sticker selection modal
   - `composeModal` - Message composition modal
   - `tradeModalTitle`, `tradeModalSubtitle`, `tradeModalIcon`, `tradeModalCount`
   - `tradeModalGrid` - Sticker grid container
   - `selectionCount` - Selected sticker counter
   - `contactTradeBtn` - Contact button (enabled/disabled)
   - `composeRecipient` - Recipient name display
   - `composeStickersGrid` - Selected stickers preview
   - `tradeMessage` - Message textarea
   - `sendTradeBtn` - Send button
   - `successToast` - Success notification

4. **Global functions exposed to window**:
   - `openTradeModal(element)` - Opens trade modal
   - `toggleStickerSelection(element, stickerId)` - Selects/deselects sticker
   - `closeTradeModal()` - Closes trade modal
   - `openComposeModal()` - Opens compose modal
   - `closeComposeModal()` - Closes compose modal
   - `sendTradeMessage()` - Sends API request
   - `clearSearch()` - Clears search input

### album/templates/album.html

1. **Sticker toggles**: Each sticker has checkbox with `data-sticker-id`
2. **Duplicate counters**: +/- buttons update numeric input
3. **Team toggle**: Selects/deselects all stickers for a team
4. **No inline JS**: Uses event delegation in app.js

### album/templates/base.html

1. **Context processor**: `team_pages` injected from `config.team_pages_by_code()`
2. **Unread messages**: Fetches `/auth/api/messages/unread-count` every 30 seconds
3. **Logout link**: In user dropdown menu

## Database Models

### User
- `id`, `username`, `email`, `password_hash`
- `photo_url`, `country`, `star_count`
- `email_verified`, `created_at`

### Message
- `id`, `sender_id`, `recipient_id`
- `content`, `is_read`, `created_at`
- `trade_id` (optional link to trade)

### Trade
- `id`, `initiator_id`, `recipient_id`
- `status` (pending/accepted/rejected/completed)
- `stickers_requested`, `stickers_offered` (JSON strings)
- `confirmed_by_initiator`, `confirmed_by_recipient`

### UserSticker
- `user_id`, `sticker_id`
- `is_owned`, `duplicate_count`

## Common Issues and Solutions

### "openTradeModal is not defined"
**Cause**: Function not exposed to global scope or script loaded after HTML
**Fix**: Ensure `window.openTradeModal = openTradeModal;` exists and script is at top

### "Cannot set properties of null (setting 'textContent')"
**Cause**: JavaScript looking for element ID that doesn't exist
**Fix**: Verify HTML element IDs match JavaScript `getElementById` calls

### "Recipient is required" API error
**Cause**: Frontend sends `recipient` but backend expects `recipient_username`
**Fix**: Use correct field name in JSON payload

### CSS styles not applying
**Cause**: Selector specificity or missing class
**Fix**: Use browser DevTools to inspect element classes

## Testing Protocol

**BEFORE committing any changes**:

1. Read this file
2. Read TEST_CHECKLIST.md
3. Test ALL related features manually
4. Check browser console for errors

## Deployment Branches

```
main        → Development/staging
uat         → User Acceptance Testing
production  → Live site
```

**Always push to all three branches** after changes:
```bash
git push origin main
git checkout uat && git merge main && git push origin uat
git checkout production && git merge main && git push origin production
```

## Environment Variables

Required in production (Railway):
- `DATABASE_URL` - PostgreSQL connection string
- `FLASK_SECRET_KEY` or `SECRET_KEY` - Session encryption
- `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD` - Email SMTP

## Contact

If unsure about any change:
1. Check this file
2. Check TEST_CHECKLIST.md
3. Ask before implementing

---

**Last updated**: 2026-03-30
**Next review**: Before every code change
