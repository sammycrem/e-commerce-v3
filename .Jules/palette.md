## 2025-05-15 - [Icon Button Accessibility & Feedback]
**Learning:** Icon-only buttons (like search, trash, or quantity controls) are invisible to screen readers without explicit ARIA labels. Users also need immediate feedback for async actions like "Add to Cart" to prevent confusion and double-clicks.
**Action:** Always include `aria-label` for icon buttons and implement a loading state (spinner/text change) for any button triggering a network request.
