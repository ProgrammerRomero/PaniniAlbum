# Testing Checklist for Panini Album

> **Rule**: Before committing ANY changes, verify ALL items on this checklist.

## Pre-Implementation

- [ ] Read existing code that might be affected
- [ ] Identify shared functions, CSS classes, DOM elements
- [ ] Check backend API expected fields match frontend
- [ ] Note any inline `onclick` handlers

## Implementation

- [ ] Make minimal changes
- [ ] Don't rename existing functions/classes without updating ALL call sites
- [ ] Add new CSS classes instead of modifying existing ones
- [ ] Keep JavaScript functions exposed to window scope if used by inline handlers

## Post-Implementation Testing

### Authentication Pages
- [ ] Register new user works
- [ ] Login works
- [ ] Logout works
- [ ] Password reset email sends

### Album Page
- [ ] Click sticker toggles owned status
- [ ] Duplicate counter +/- buttons work
- [ ] Team toggle (select all) works
- [ ] Progress bar updates
- [ ] Stats modal shows correct data

### Navigation (Navbar)
- [ ] Teams dropdown shows above page content (not behind)
- [ ] Export dropdown shows above page content
- [ ] User dropdown shows above page content
- [ ] On login page: Teams dropdown is hidden
- [ ] On login page: Logo is not clickable (no link)
- [ ] On register page: Teams dropdown is hidden
- [ ] On register page: Logo is not clickable (no link)
- [ ] On other pages: Teams dropdown is visible
- [ ] On other pages: Logo is clickable

### Other Users Page (CRITICAL - frequently breaks)
- [ ] Page loads without JavaScript errors
- [ ] Search by username works (partial match, e.g., "jo" finds "john")
- [ ] Search by sticker ID works (partial match, e.g., "bra" finds "bra-17")
- [ ] Search bar stays sticky at top when scrolling
- [ ] Clear search button (✕) works
- [ ] Card layout stays in grid formation when filtering (not messy/stacked)
- [ ] After clearing search, cards return to original 5-column grid layout
- [ ] Click trader card opens modal with blurred backdrop
- [ ] Click "You Can Get" opens trade modal
- [ ] Click "You Can Give" opens trade modal
- [ ] Stickers are NOT pre-selected (start unchecked)
- [ ] Clicking sticker selects it (checkbox checked)
- [ ] Selection count updates
- [ ] "Contact for Trade" button enables after selection
- [ ] Compose modal opens with correct recipient
- [ ] Send message succeeds (no "recipient is required" error)
- [ ] Success toast shows after sending

### Messages
- [ ] Inbox loads
- [ ] Can view message thread
- [ ] Can reply to message
- [ ] Unread badge updates

### Profile
- [ ] Profile page loads
- [ ] Can update photo
- [ ] Can update country
- [ ] Can change password

## Browser Console Check

- [ ] No "undefined" function errors
- [ ] No "Cannot set property of null" errors
- [ ] No 400/404/500 API errors

## Final Verification

- [ ] Test in both desktop and mobile view (if applicable)
- [ ] Hard refresh browser (Ctrl+F5) to clear cache
- [ ] Check all features work after full page reload

---

**Remember**: A fix that breaks another feature is not a fix. Test everything.
