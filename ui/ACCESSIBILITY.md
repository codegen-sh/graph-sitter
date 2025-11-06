# Accessibility Guidelines

The Graph-Sitter UI is designed to be fully accessible and compliant with WCAG 2.1 Level AA standards.

## Keyboard Navigation

### Global Shortcuts
- `Tab` / `Shift+Tab` - Navigate between interactive elements
- `Enter` / `Space` - Activate buttons and links
- `Escape` - Close modals, dialogs, and overlays
- `Arrow Keys` - Navigate within lists and menus

### Component-Specific
- **Sidebar**: Use Tab to navigate menu items, Enter to select
- **Codemod List**: Arrow keys to navigate, Enter to select
- **File Browser**: Arrow keys to expand/collapse folders
- **Search**: Type to search, Escape to clear

## Screen Reader Support

### Semantic HTML
All components use semantic HTML elements:
- `<nav>` for navigation
- `<main>` for main content
- `<header>` for page headers
- `<button>` for actions
- `<a>` for links

### ARIA Labels
Every interactive element has appropriate ARIA labels:
```tsx
<Button aria-label="Execute codemod">
  <Play className="h-4 w-4" />
</Button>
```

### Live Regions
Dynamic content updates use ARIA live regions:
```tsx
<div role="status" aria-live="polite" aria-atomic="true">
  {statusMessage}
</div>
```

### Landmarks
Page structure uses ARIA landmarks:
- `role="navigation"` for sidebar
- `role="main"` for content area
- `role="contentinfo"` for status bar

## Visual Accessibility

### Color Contrast
All text meets minimum contrast ratios:
- Normal text: 4.5:1
- Large text (18pt+): 3:1
- UI components: 3:1

### Focus Indicators
All interactive elements have visible focus indicators:
```css
*:focus-visible {
  outline: none;
  ring: 2px solid hsl(var(--ring));
  ring-offset: 2px;
}
```

### Color Independence
Information is never conveyed by color alone:
- Status indicators use icons + color
- Diffs use +/- symbols + color
- Errors include text + icon

## Motion and Animation

### Reduced Motion
Respects user preferences:
```css
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

### Animation Controls
- Animations are subtle and purposeful
- No auto-playing animations
- All animations can be disabled

## Form Accessibility

### Labels
All form inputs have associated labels:
```tsx
<label htmlFor="branch-name">Branch Name</label>
<Input id="branch-name" />
```

### Error Messages
Errors are clearly communicated:
```tsx
<Input
  aria-invalid={hasError}
  aria-describedby={hasError ? "error-message" : undefined}
/>
{hasError && (
  <span id="error-message" role="alert">
    {errorMessage}
  </span>
)}
```

### Required Fields
Required fields are clearly marked:
```tsx
<label>
  Branch Name <span aria-label="required">*</span>
</label>
```

## Testing Accessibility

### Manual Testing Checklist

#### Keyboard Navigation
- [ ] All interactive elements are reachable via keyboard
- [ ] Tab order is logical
- [ ] Focus is visible on all elements
- [ ] No keyboard traps
- [ ] Shortcuts don't conflict

#### Screen Reader Testing
- [ ] All content is announced correctly
- [ ] Navigation is clear and logical
- [ ] Images have alt text
- [ ] Forms are properly labeled
- [ ] Errors are announced

#### Visual Testing
- [ ] Sufficient color contrast
- [ ] Content is readable at 200% zoom
- [ ] Layout doesn't break at different sizes
- [ ] Focus indicators are visible
- [ ] No horizontal scrolling (mobile)

### Automated Testing

#### axe-core
Install and use axe-core for automated testing:

```bash
npm install @axe-core/react
```

Add to app:
```tsx
if (process.env.NODE_ENV !== 'production') {
  import('@axe-core/react').then((axe) => {
    axe.default(React, ReactDOM, 1000);
  });
}
```

#### Jest Tests
Include accessibility tests:
```tsx
import { axe, toHaveNoViolations } from 'jest-axe';
expect.extend(toHaveNoViolations);

test('component should not have accessibility violations', async () => {
  const { container } = render(<Component />);
  const results = await axe(container);
  expect(results).toHaveNoViolations();
});
```

## Common Patterns

### Skip to Main Content
```tsx
<a href="#main-content" className="skip-to-main">
  Skip to main content
</a>
```

### Loading States
```tsx
<Button disabled aria-busy="true">
  <Loader className="animate-spin" />
  <span className="sr-only">Loading...</span>
</Button>
```

### Empty States
```tsx
<div className="empty-state" role="status">
  <p>No items found</p>
</div>
```

### Error States
```tsx
<div role="alert" className="error-state">
  <AlertCircle aria-hidden="true" />
  <span>{errorMessage}</span>
</div>
```

## Resources

- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [ARIA Authoring Practices](https://www.w3.org/WAI/ARIA/apg/)
- [WebAIM Keyboard Testing](https://webaim.org/articles/keyboard/)
- [axe DevTools](https://www.deque.com/axe/devtools/)

## Reporting Issues

If you encounter accessibility issues:
1. Check if it's covered in this guide
2. Test with multiple assistive technologies
3. Report with specific details:
   - Component affected
   - Assistive technology used
   - Expected vs actual behavior
   - Steps to reproduce
