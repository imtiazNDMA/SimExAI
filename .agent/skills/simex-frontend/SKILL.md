---
name: SimEx Frontend Development
description: Frontend engineering guide for the SimEx AI chatbot — vanilla HTML/JS/CSS chat interface, timeline dashboard, wing selector panels, and responsive design system.
---

# SimEx Frontend Development

Instructions for building and maintaining the SimEx AI frontend using vanilla HTML, JavaScript, and CSS.

## Technology Stack

| Component | Technology |
|---|---|
| **Structure** | HTML5 semantic elements |
| **Logic** | Vanilla JavaScript (ES modules) |
| **Styling** | CSS3 with custom properties |
| **API** | Fetch API for REST calls |

## Project Structure

```
frontend/
├── index.html    # Single-page application shell
├── style.css     # Complete design system + component styles
└── app.js        # Application logic, API calls, DOM manipulation
```

## UI Layout

```
┌──────────────────────────────────────────────────────┐
│  Header: SimEx AI — Earthquake Batagram KP M7.4      │
├────────────┬─────────────────────────┬───────────────┤
│            │                         │               │
│  Wing      │     Chat Area           │   Timeline    │
│  Selector  │                         │   & Status    │
│  Panel     │  [Messages]             │   Panel       │
│            │  [Messages]             │               │
│  • Tech EW │  [Messages]             │  ● D-90       │
│  • Ops Wing│                         │  ○ D-30       │
│  • Logist. │  ┌──────────────────┐   │  ○ D-Day      │
│  • DRR     │  │ Type message...  │   │  ○ D+30       │
│  • GCC     │  └──────────────────┘   │  ○ D+90       │
│  • PCC     │                         │               │
│  • Tech EM │                         │  [Injects]    │
│  • Military│                         │               │
│  • NIDM    │                         │               │
│  • Infra   │                         │               │
│            │                         │               │
├────────────┴─────────────────────────┴───────────────┤
│  Footer: Current Phase • Active Wing • Status        │
└──────────────────────────────────────────────────────┘
```

## Design System

### Color Palette (CSS Custom Properties)

```css
:root {
    /* Primary — NDMA green/teal tones */
    --color-primary: #0d7377;
    --color-primary-light: #14a3a8;
    --color-primary-dark: #095255;
    
    /* Accent — Alert/action colors */
    --color-danger: #dc3545;
    --color-warning: #f0ad4e;
    --color-success: #28a745;
    --color-info: #17a2b8;
    
    /* Neutrals */
    --color-bg: #0f1923;
    --color-surface: #1a2836;
    --color-surface-hover: #243447;
    --color-text: #e8edf2;
    --color-text-muted: #8899aa;
    --color-border: #2d3f50;
    
    /* Typography */
    --font-primary: 'Inter', system-ui, sans-serif;
    --font-mono: 'JetBrains Mono', monospace;
    
    /* Spacing */
    --space-xs: 4px;
    --space-sm: 8px;
    --space-md: 16px;
    --space-lg: 24px;
    --space-xl: 32px;
    
    /* Borders */
    --radius-sm: 6px;
    --radius-md: 10px;
    --radius-lg: 16px;
}
```

### Key UI Components

1. **Wing Selector** — Vertical list with icons, highlights active wing
2. **Chat Area** — Message bubbles (user = right, system = left), auto-scroll
3. **Timeline Panel** — Vertical phase stepper with active/completed states
4. **Inject Cards** — Timed event notifications that appear per phase
5. **Phase Advance Button** — Prominent CTA to progress the exercise

### Interactions

- Click wing → loads wing context, updates chat
- Send message → POST to `/api/chat`, display response
- Advance phase → POST to `/api/phase/advance`, update timeline, load new injects
- Inject cards animate in when phase changes

## Responsive Design

- **Desktop** (>1024px): 3-column layout (sidebar | chat | timeline)
- **Tablet** (768–1024px): 2-column (chat | collapsible panels)
- **Mobile** (<768px): Single column, bottom nav for wing/timeline switching

## API Integration

All API calls go to `http://localhost:8000/api/`:

```javascript
const API_BASE = 'http://localhost:8000/api';

async function sendMessage(wingId, phaseId, message) {
    const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ wing_id: wingId, phase_id: phaseId, message })
    });
    return res.json();
}
```

## Accessibility

- Semantic HTML: `<nav>`, `<main>`, `<aside>`, `<article>`
- ARIA labels on interactive elements
- Keyboard navigation for wing selector
- Focus management after messages
- High contrast color ratios (WCAG AA minimum)
