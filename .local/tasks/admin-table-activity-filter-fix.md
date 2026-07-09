# Fix users table display & activity filters

## What & Why
The admin Users table gets cut off / doesn't display cleanly on smaller screens (columns run off the edge with no way to scroll to see them, per the attached screenshot). Separately, the Overview tab's "Recent Activity" feed already has a free-text "Filter by user..." box, but admins want a proper list of actual users to pick from (not free typing) plus a quick way to jump into that user's full analytics from the activity feed, so they don't have to leave Overview and hunt for the person in the Users tab.

## Done looks like
- The Users table (Admin > Users) is fully readable at common screen widths: either all columns fit without clipping, or the table scrolls horizontally within its own container without breaking the page layout.
- The "Recent Activity" filter on Overview lets an admin pick a user from an actual list/dropdown of existing users (e.g. autocomplete or select) instead of only free-text typing.
- From an activity item (or from the user filter), an admin can click through to that user's analytics drill-down panel (the same one used from the Users tab) without re-navigating manually.

## Out of scope
- Any change to what data is tracked/aggregated (covered by a separate task if needed).
- Redesigning the Users table's columns/metrics themselves.

## Steps
1. **Fix table overflow** — Make the Users table container handle overflow properly (horizontal scroll or responsive column handling) so no column is invisible/cut off on typical laptop/admin screen widths.
2. **User-picker for activity filter** — Replace or augment the free-text "Filter by user" input in Recent Activity with a selectable list of real users (fetched from the existing users endpoint), keeping it fast for admins with many users (e.g. searchable dropdown).
3. **Link activity to analytics** — Add a way to open the existing per-user analytics drill-down panel directly from the Recent Activity section (e.g. from the user picker or from an activity row), reusing the existing analytics panel/component rather than building a new one.

## Relevant files
- `Frontend/src/components/ui/admin/users-tab.tsx`
- `Frontend/src/components/ui/admin/overview-tab.tsx`
- `Frontend/src/components/ui/admin/user-analytics-panel.tsx`
- `Frontend/src/api.ts:715-731,934-1018`
