# UI/UX Standards

> **Scope:** All Product Forge user interfaces (web, mobile)
> **Source:** WCAG 2.1 AA + Material Design + Apple HIG + Nielsen Heuristics
> **Version:** 1.0 | **Date:** 2026-08-24

---

## 1. Accessibility (WCAG 2.1 AA) - MANDATORY

### 1.1 Perceivable
- **Text alternatives:** All images have alt text
- **Captions:** Videos have captions
- **Color contrast:** 4.5:1 for normal text, 3:1 for large text
- **Resize:** Text resizable to 200% without loss of functionality

### 1.2 Operable
- **Keyboard accessible:** All functionality available via keyboard
- **No seizures:** No content flashes more than 3 times/second
- **Navigable:** Skip links, page titles, focus order, link purpose
- **Input modes:** Multiple input methods (click, touch, voice)

### 1.3 Understandable
- **Readable:** Language declared, unusual words explained
- **Predictable:** Consistent navigation, no unexpected changes
- **Input assistance:** Error identification, labels, instructions

### 1.4 Robust
- **Compatible:** Works with assistive technologies
- **Valid HTML:** Semantic markup
- **ARIA:** Proper use of ARIA attributes

---

## 2. Semantic HTML

### 2.1 Use the Right Element
```tsx
// Good: Semantic HTML
<header>
  <nav>
    <ul>
      <li><a href="/">Home</a></li>
      <li><a href="/about">About</a></li>
    </ul>
  </nav>
</header>

<main>
  <article>
    <h1>Article Title</h1>
    <p>Content...</p>
  </article>
</main>

<footer>...</footer>

// Bad: Divs everywhere
<div class="header">
  <div class="nav">
    <div class="link">Home</div>
  </div>
</div>
```

### 2.2 Heading Hierarchy
```tsx
// Good: Sequential headings
<h1>Page Title</h1>
  <h2>Section</h2>
    <h3>Subsection</h3>
  <h2>Another Section</h2>

// Bad: Skipping levels
<h1>Title</h1>
<h3>Skipped h2!</h3>
```

### 2.3 Lists
```tsx
// Use <ul> for unordered, <ol> for ordered
<ul>
  <li>Item 1</li>
  <li>Item 2</li>
</ul>

// Use <dl> for description lists
<dl>
  <dt>Term</dt>
  <dd>Definition</dd>
</dl>
```

---

## 3. ARIA (When HTML Isn't Enough)

### 3.1 When to Use ARIA
- Custom widgets (not native HTML)
- Dynamic content
- Complex interactions

### 3.2 When NOT to Use ARIA
- Native HTML elements exist
- ARIA duplicates native semantics

### 3.3 Common ARIA Patterns
```tsx
// Button (use <button> instead if possible)
<div role="button" tabIndex={0} onKeyDown={handleEnter}>
  Click me
</div>

// Dialog/Modal
<div role="dialog" aria-labelledby="title" aria-describedby="description">
  <h2 id="title">Confirm Action</h2>
  <p id="description">Are you sure?</p>
</div>

// Live region for dynamic updates
<div aria-live="polite" aria-atomic="true">
  {statusMessage}
</div>

// Loading state
<button aria-busy={isLoading} aria-label="Save">
  {isLoading ? 'Saving...' : 'Save'}
</button>
```

---

## 4. Forms

### 4.1 Labels (Mandatory)
```tsx
// Good: Associated label
<label htmlFor="email">Email</label>
<input id="email" type="email" name="email" />

// Or implicit label
<label>
  Email
  <input type="email" name="email" />
</label>

// Bad: No label
<input type="email" placeholder="Email" />
```

### 4.2 Error Messages
```tsx
<div>
  <label htmlFor="email">Email</label>
  <input
    id="email"
    type="email"
    aria-invalid={hasError}
    aria-describedby={hasError ? "email-error" : undefined}
  />
  {hasError && (
    <p id="email-error" role="alert">
      Please enter a valid email address
    </p>
  )}
</div>
```

### 4.3 Required Fields
```tsx
<label htmlFor="name">
  Name <span aria-label="required">*</span>
</label>
<input id="name" required aria-required="true" />
```

### 4.4 Fieldsets & Legends
```tsx
<fieldset>
  <legend>Shipping Address</legend>
  <label>
    Street
    <input type="text" name="street" />
  </label>
  <label>
    City
    <input type="text" name="city" />
  </label>
</fieldset>
```

---

## 5. Keyboard Navigation

### 5.1 Focus Management
```tsx
// Visible focus indicator (don't remove outline!)
button:focus-visible {
  outline: 2px solid #3b82f6;
  outline-offset: 2px;
}

// Focus trap in modal
function Modal({ children, onClose }) {
  const firstFocusableRef = useRef(null);
  const lastFocusableRef = useRef(null);
  
  useEffect(() => {
    firstFocusableRef.current?.focus();
    
    function handleTab(e) {
      if (e.key === 'Tab') {
        if (e.shiftKey && document.activeElement === firstFocusableRef.current) {
          e.preventDefault();
          lastFocusableRef.current?.focus();
        } else if (!e.shiftKey && document.activeElement === lastFocusableRef.current) {
          e.preventDefault();
          firstFocusableRef.current?.focus();
        }
      }
      if (e.key === 'Escape') onClose();
    }
    
    document.addEventListener('keydown', handleTab);
    return () => document.removeEventListener('keydown', handleTab);
  }, [onClose]);
  
  return (
    <div role="dialog" aria-modal="true">
      {children(/* refs */)}
    </div>
  );
}
```

### 5.2 Skip Links
```tsx
<a href="#main-content" className="skip-link">
  Skip to main content
</a>

<main id="main-content">...</main>
```

### 5.3 Keyboard Shortcuts
- `Tab` / `Shift+Tab` — Navigate
- `Enter` / `Space` — Activate button
- `Esc` — Close modal/dropdown
- `Arrow keys` — Navigate within component
- `Cmd/Ctrl + K` — Command palette (if applicable)

---

## 6. Color & Contrast

### 6.1 Contrast Ratios (WCAG AA)
| Element | Min Ratio |
|---|---|
| Normal text (< 18pt) | 4.5:1 |
| Large text (≥ 18pt or 14pt bold) | 3:1 |
| UI components & graphics | 3:1 |
| Incidental (logos, decorative) | None |

### 6.2 Don't Rely on Color Alone
```tsx
// Bad: Only color indicates error
<input style={{ borderColor: hasError ? 'red' : 'gray' }} />

// Good: Color + icon + text
<div>
  <input
    style={{ borderColor: hasError ? 'red' : 'gray' }}
    aria-invalid={hasError}
  />
  {hasError && (
    <span>
      <ErrorIcon /> Invalid email
    </span>
  )}
</div>
```

### 6.3 Dark Mode
- Provide both light and dark modes
- Test contrast in both modes
- Use CSS variables for theming

```css
:root {
  --bg-primary: #ffffff;
  --text-primary: #000000;
  --border: #e5e7eb;
}

[data-theme="dark"] {
  --bg-primary: #1a1a1a;
  --text-primary: #ffffff;
  --border: #374151;
}
```

---

## 7. Responsive Design

### 7.1 Mobile-First
```css
/* Base styles (mobile) */
.container {
  padding: 1rem;
  font-size: 1rem;
}

/* Tablet */
@media (min-width: 768px) {
  .container {
    padding: 2rem;
    font-size: 1.125rem;
  }
}

/* Desktop */
@media (min-width: 1024px) {
  .container {
    padding: 3rem;
    font-size: 1.25rem;
  }
}
```

### 7.2 Breakpoints (Tailwind)
```tsx
<div className="
  px-4 py-2          /* mobile */
  md:px-6 md:py-3    /* tablet */
  lg:px-8 lg:py-4    /* desktop */
  xl:px-10           /* large desktop */
">
```

### 7.3 Touch Targets
- Minimum 44x44px (iOS) or 48x48dp (Android)
- Adequate spacing between interactive elements
- Use `min-h-[44px] min-w-[44px]`

---

## 8. Loading & Error States

### 8.1 Loading States
```tsx
// Skeleton screens (not spinners for content)
function TodoListSkeleton() {
  return (
    <div>
      {[1, 2, 3].map(i => (
        <div key={i} className="animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-3/4" />
          <div className="h-3 bg-gray-200 rounded w-1/2 mt-2" />
        </div>
      ))}
    </div>
  );
}

// Spinner for short operations
function Button({ isLoading, children }) {
  return (
    <button disabled={isLoading} aria-busy={isLoading}>
      {isLoading ? <Spinner /> : children}
    </button>
  );
}
```

### 8.2 Empty States
```tsx
function EmptyTodos() {
  return (
    <div className="text-center py-12">
      <EmptyIcon className="mx-auto h-12 w-12 text-gray-400" />
      <h3 className="mt-2 text-sm font-medium">No todos</h3>
      <p className="mt-1 text-sm text-gray-500">
        Get started by creating a new todo.
      </p>
      <button className="mt-4 btn-primary">New Todo</button>
    </div>
  );
}
```

### 8.3 Error States
```tsx
function ErrorMessage({ error, onRetry }) {
  return (
    <div role="alert" className="bg-red-50 border border-red-200 rounded p-4">
      <div className="flex">
        <ErrorIcon className="h-5 w-5 text-red-400" />
        <div className="ml-3">
          <h3 className="text-sm font-medium text-red-800">
            Something went wrong
          </h3>
          <p className="mt-1 text-sm text-red-700">{error.message}</p>
          {onRetry && (
            <button onClick={onRetry} className="mt-2 btn-sm">
              Try Again
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
```

---

## 9. Component Library

### 9.1 Component Anatomy
```tsx
// components/ui/Button.tsx
import { cva, type VariantProps } from 'class-variance-authority';
import { forwardRef, type ButtonHTMLAttributes } from 'react';

const buttonVariants = cva(
  'inline-flex items-center justify-center rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none',
  {
    variants: {
      variant: {
        primary: 'bg-blue-600 text-white hover:bg-blue-700',
        secondary: 'bg-gray-200 text-gray-900 hover:bg-gray-300',
        ghost: 'bg-transparent hover:bg-gray-100',
        danger: 'bg-red-600 text-white hover:bg-red-700',
      },
      size: {
        sm: 'h-9 px-3 text-sm',
        md: 'h-10 px-4 text-base',
        lg: 'h-11 px-6 text-lg',
      },
    },
    defaultVariants: { variant: 'primary', size: 'md' },
  }
);

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof buttonVariants>;

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button
      ref={ref}
      className={buttonVariants({ variant, size, className })}
      {...props}
    />
  )
);
Button.displayName = 'Button';
```

### 9.2 Composition Pattern
```tsx
// Compose complex components from simple ones
function ConfirmDialog({ isOpen, onConfirm, onCancel, title, message }) {
  if (!isOpen) return null;
  
  return (
    <Modal onClose={onCancel}>
      <ModalHeader>{title}</ModalHeader>
      <ModalBody>{message}</ModalBody>
      <ModalFooter>
        <Button variant="ghost" onClick={onCancel}>Cancel</Button>
        <Button variant="primary" onClick={onConfirm}>Confirm</Button>
      </ModalFooter>
    </Modal>
  );
}
```

---

## 10. Design Tokens

### 10.1 Tailwind Config
```js
// tailwind.config.ts
export default {
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
        },
      },
      spacing: {
        'xs': '0.5rem',
        'sm': '0.75rem',
        'md': '1rem',
        'lg': '1.5rem',
        'xl': '2rem',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        'sm': '0.25rem',
        'md': '0.5rem',
        'lg': '0.75rem',
      },
    },
  },
};
```

### 10.2 CSS Variables (for theming)
```css
:root {
  --color-primary: 59 130 246;
  --color-text: 17 24 39;
  --color-bg: 255 255 255;
  --space-1: 0.25rem;
  --space-2: 0.5rem;
  --radius-md: 0.5rem;
}
```

---

## 11. Animation & Motion

### 11.1 Respect User Preferences
```css
/* Respect reduced motion preference */
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

### 11.2 Purposeful Animation
- **Do:** Loading indicators, state transitions, drawing attention
- **Don't:** Decorative only, excessive, slow (> 500ms)

### 11.3 Performance
- Use `transform` and `opacity` (GPU-accelerated)
- Avoid animating `width`, `height`, `top`, `left` (causes reflow)
- Use `will-change` sparingly

---

## 12. Internationalization (i18n)

### 12.1 Externalize Strings
```tsx
// Bad
<button>Save</button>

// Good
<button>{t('common.save')}</button>
```

### 12.2 RTL Support
```css
/* Use logical properties */
.container {
  margin-inline-start: 1rem;  /* Works in LTR and RTL */
  padding-inline-end: 2rem;
}
```

### 12.3 Date/Time/Number Formatting
```tsx
// Use Intl APIs
const date = new Intl.DateTimeFormat(locale).format(new Date());
const number = new Intl.NumberFormat(locale).format(1234.56);
const currency = new Intl.NumberFormat(locale, {
  style: 'currency',
  currency: 'USD',
}).format(99.99);
```

---

## 13. Performance

### 13.1 Image Optimization
```tsx
import Image from 'next/image';

<Image
  src="/hero.jpg"
  alt="Hero image"
  width={1200}
  height={600}
  priority  /* For above-the-fold images */
  placeholder="blur"
  blurDataURL={blurDataUrl}
/>
```

### 13.2 Code Splitting
```tsx
import { lazy, Suspense } from 'react';

const HeavyComponent = lazy(() => import('./HeavyComponent'));

function App() {
  return (
    <Suspense fallback={<Skeleton />}>
      <HeavyComponent />
    </Suspense>
  );
}
```

### 13.3 Bundle Size
- Monitor with `webpack-bundle-analyzer`
- Lazy load routes
- Tree-shake unused code
- Use dynamic imports for large libraries

---

## 14. Anti-Patterns to Avoid

| Anti-Pattern | Why | Instead |
|---|---|---|
| `onClick` on non-button | Not accessible | Use `<button>` |
| Removing outline | Breaks keyboard nav | Use `:focus-visible` |
| Placeholder as label | Disappears, bad for a11y | Use `<label>` |
| Color-only error indication | Color-blind users miss it | Icon + text + color |
| Tiny touch targets | Hard to tap | Min 44x44px |
| Auto-playing media | Annoying, bad for a11y | Require user action |
| Infinite scroll without alternative | Can't reach footer | Pagination option |
| Modal without focus trap | Keyboard users escape | Trap focus in modal |
| Loading spinner forever | No feedback if error | Timeout + error state |
| Custom form validation without a11y | Screen readers miss errors | aria-invalid + aria-describedby |
| `div` soup | Not semantic | Use semantic HTML |
| Non-descriptive link text "Click here" | Bad for screen readers | Descriptive text |

---

## 15. References

- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [MDN Web Docs - Accessibility](https://developer.mozilla.org/en-US/docs/Web/Accessibility)
- [Material Design Guidelines](https://material.io/design)
- [Apple Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/)
- [Nielsen Norman Group - 10 Usability Heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/)
- [WebAIM](https://webaim.org/)
- [A11y Project Checklist](https://www.a11yproject.com/checklist/)

---

## 16. Enforcement

- **ESLint plugins:** `eslint-plugin-jsx-a11y`
- **Automated testing:** axe-core, Pa11y in CI
- **Manual testing:** Keyboard, screen reader, contrast checker
- **Code review:** Accessibility check on every PR
- **Lighthouse audits:** Run in CI, target 95+ accessibility score
