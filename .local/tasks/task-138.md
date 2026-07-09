---
title: Let admins filter Recent Activity and Security signups by date range or user
---
**What & Why**
The Overview tab's Recent Activity feed and the Security tab's signup/suspension lists currently show a fixed recent window with no filtering. As the user base grows, admins will want to search/filter these lists (by date range, username, or activity type) rather than scroll a flat recent-N list.

**Done looks like**
- [ ] Backend /admin/activity and /admin/security support optional date-range and type/status query params
- [ ] Frontend Overview and Security tabs expose simple filter controls wired to those params

**Relevant files**
- /home/runner/workspace/Backend/src/main.py
- /home/runner/workspace/Backend/src/services/chat_service.py
- /home/runner/workspace/Frontend/src/components/ui/admin/overview-tab.tsx
- /home/runner/workspace/Frontend/src/components/ui/admin/security-tab.tsx