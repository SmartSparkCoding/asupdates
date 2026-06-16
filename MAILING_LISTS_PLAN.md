# Mailing Lists Plan

## Goal

Add an admin-facing mailing lists system for modern school communications. The feature should make it easy to create targeted lists, reuse polished email layouts, and send either guided rich-text emails or fully manual HTML emails.

## Product Shape

- A modern / sleek mailing-lists dashboard inside the admin area.
- Expandable list controls so admins can open a list and work on it without leaving the page.
- Support for creating a new list or selecting an existing list.
- Support for adding, removing, viewing, and editing users in a list.
- Support for a shared footer that appears on every mailing-list email.

## Core Email Modes

### Premade Email Mode

This mode should provide structured fields for common newsletter content:

- Title
- Subject
- Main body
- Signature

The UI should feel guided and polished so staff can produce consistent emails quickly.

### Manual HTML Mode

This mode should allow direct HTML editing for power users.

- Permit placeholders such as {(user_name)}.
- Replace placeholders per recipient at send time.
- Keep the shared footer appended automatically unless a list-specific override is explicitly enabled.

## Mailing List Management

- Create a list with a name, description, and optional tags or audience notes.
- Select one or more existing users for the list.
- Add and remove users from the list from the admin interface.
- Allow admins to inspect the current list membership before sending.
- Store list membership in a durable database table rather than only in memory.

## Template And Styling Direction

- Build the mailing-lists UI to match the existing control-centre aesthetic.
- Use a clean, high-contrast card layout with clear section headings.
- Keep the editor surfaces spacious and uncluttered.
- Reuse the same visual language as the admin dashboard so the feature feels native.

## Recommended Data Model

- `mailing_lists`: id, name, description, footer_html, created_at, updated_at.
- `mailing_list_members`: list_id, user_id, created_at.
- `mailing_list_drafts` or `mailing_list_messages`: list_id, mode, title, subject, body_html, signature_html, manual_html, created_at, updated_at.
- Optional send log table for auditing who was sent what and when.

## Sending Flow

1. Admin opens the mailing-lists dashboard.
2. Admin creates or selects a list.
3. Admin edits membership if needed.
4. Admin chooses Premade or Manual HTML mode.
5. Admin previews the final rendered email for a sample recipient.
6. Admin sends the email to the full list.
7. System records the send in a log for traceability.

## Placeholder Rules

- Resolve `{(user_name)}` to the recipient's display name.
- Allow future list-specific placeholders if needed, but keep the initial set minimal.
- Escape or sanitize content appropriately depending on the mode.

## Shared Footer

- The footer should be editable from the mailing-lists area.
- The footer should be included in every list email by default.
- Allow the footer to carry contact details, unsubscribe guidance, or school branding.

## Implementation Phases

### Phase 1

- Add database tables for lists, members, drafts, and logs.
- Add admin routes and templates for list management.
- Add simple preview and send plumbing.

### Phase 2

- Build the polished premade editor.
- Build the manual HTML editor.
- Add placeholder substitution and per-recipient rendering.

### Phase 3

- Add list auditing, send history, and safer preview tooling.
- Polish the UI and tighten validation.

## Acceptance Criteria

- Admins can create and manage mailing lists from the dashboard.
- Admins can choose between premade and manual HTML email composition.
- Recipient placeholders render correctly for each user.
- The shared footer appears on all mailing-list emails.
- The UI matches the rest of the site and feels like part of the same product.
