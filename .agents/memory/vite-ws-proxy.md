---
name: Vite WebSocket proxy fix
description: Vite proxy needs ws:true to forward WebSocket upgrade requests to the backend
---

## Rule
Always include `ws: true` in every Vite proxy rule that handles WebSocket paths.

```ts
proxy: {
  '/sciparser': {
    target: 'http://localhost:8000',
    changeOrigin: true,
    ws: true,   // ← required for WS upgrade forwarding
  },
},
```

**Why:** Without `ws: true`, Vite's `http-proxy` silently drops WebSocket upgrade
requests for path-based proxy rules. The browser's `new WebSocket(...)` call connects
to Vite's own HMR endpoint instead of the backend. `ws.onopen` never fires; the
connection immediately closes. No error is thrown — it looks like the WS connected
and then disconnected. All frame broadcasts to `browser_connections` go nowhere
(`connections=0` or messages to a dead socket that gets cleaned up on next send).

**How to apply:** Any time a FastAPI (or other backend) WebSocket endpoint is reached
through a Vite dev-server proxy rule, that rule must have `ws: true`.
