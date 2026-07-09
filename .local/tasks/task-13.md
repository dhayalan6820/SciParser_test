---
title: Anchor chat messages to the bottom
---
# Chat messages bottom-anchor

## What & Why
Chat messages currently render from the top of the chat column downward.
When only a few messages exist there is a large blank gap between the last
message and the input bar.  Every real chat app anchors messages to the
bottom so new messages appear just above the input and older ones scroll
upward.  Also fix the chat column's `min-w-[320px]` which causes horizontal
overflow on phones narrower than 320 px.

## Done looks like
- With 1–2 messages the bubbles sit near the bottom of the chat area, just
  above the input bar — not at the top
- As more messages are added the column scrolls naturally upward
- The auto-scroll-to-latest behaviour still works after each new message
- On a 320 px-wide phone the chat column fills the screen without overflowing

## Out of scope
- Changing message bubble styles or colours
- Changing the browser / tool-log panels
- Any backend changes

## Steps
1. **Bottom-anchor the messages list** — Wrap the messages list in a flex
   column container that uses `justify-end` (or equivalent) so messages
   stack from the bottom up.  The scroll container must still allow the
   list to grow beyond the viewport and remain scrollable.
2. **Fix the chat column min-width** — Replace the hard-coded `min-w-[320px]`
   on the chat column with a smaller safe value (`min-w-0`) so phones
   narrower than 320 px do not trigger horizontal scroll.
3. **Verify auto-scroll** — Confirm the `scrollRef` / `scrollToBottom` logic
   still scrolls to the latest message after both of the above changes.

## Relevant files
- `Frontend/src/components/ui/chat_page.tsx:1917-1949`