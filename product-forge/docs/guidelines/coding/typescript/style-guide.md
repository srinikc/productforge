# TypeScript & React Coding Standards

> **Scope:** All TypeScript code in Product Forge (products/myworld/apps/*, products/myworld/packages/*)
> **Source:** Google TypeScript Style Guide + Airbnb React + Next.js docs + React Native docs
> **Version:** 1.0 | **Date:** 2026-08-24

---

## 1. TypeScript Configuration

### 1.1 Strict Mode (Mandatory)
- `"strict": true` — All strict checks enabled
- `"noUncheckedIndexedAccess": true` — Catch undefined array/object access
- `"noImplicitOverride": true` — Explicit override keyword
- `"noFallthroughCasesInSwitch": true` — Catch switch fallthrough

Base config already in `packages/config/tsconfig.base.json`.

### 1.2 Path Aliases
```json
{
  "baseUrl": ".",
  "paths": {
    "@/*": ["./src/*"],
    "@myworld/ui": ["../packages/ui/src"],
    "@myworld/types": ["../packages/types/src"]
  }
}
```

---

## 2. Naming Conventions

| Type | Convention | Example |
|---|---|---|
| **Variables** | camelCase | `userName`, `isActive` |
| **Functions** | camelCase | `getUserById`, `validateEmail` |
| **Classes** | PascalCase | `UserService`, `TodoRepository` |
| **Components** | PascalCase | `UserProfile`, `TodoList` |
| **Interfaces** | PascalCase (no `I` prefix) | `User`, `TodoItem` |
| **Type aliases** | PascalCase | `UserResponse`, `AuthState` |
| **Enums** | PascalCase | `UserRole`, `TodoStatus` |
| **Constants** | UPPER_SNAKE_CASE | `MAX_RETRIES`, `API_BASE_URL` |
| **Files (components)** | PascalCase | `UserProfile.tsx` |
| **Files (utilities)** | kebab-case | `format-date.ts`, `api-client.ts` |
| **Folders** | kebab-case | `user-profile/`, `auth-services/` |

---

## 3. Type System

### 3.1 Prefer `type` over `interface`
```typescript
// Preferred
type User = {
  id: number;
  email: string;
  name: string;
};

// Use interface only for extendable contracts
interface Repository<T> {
  get(id: number): Promise<T | null>;
  create(data: Omit<T, 'id'>): Promise<T>;
}
```

### 3.2 Use Specific Types
```typescript
// Bad
function getUser(id: any): any { ... }

// Good
function getUser(id: number): Promise<User | null> { ... }
```

### 3.3 Avoid `any`, Use `unknown` Instead
```typescript
// Bad
function parseJson(data: any): User { ... }

// Good
function parseJson(data: unknown): User {
  if (typeof data === 'object' && data !== null && 'id' in data) {
    return data as User;
  }
  throw new Error('Invalid data');
}
```

### 3.4 Use `readonly` for Immutable Data
```typescript
type UserConfig = {
  readonly id: number;
  readonly email: string;
  name: string; // mutable
};
```

### 3.5 Discriminated Unions for State
```typescript
type AsyncState<T> = 
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'error'; error: Error };
```

---

## 4. React Patterns

### 4.1 Component Structure
```tsx
// One component per file
// File name matches component name
import { useState, useEffect } from 'react';
import type { User } from '@myworld/types';

type UserProfileProps = {
  userId: number;
  onUpdate?: (user: User) => void;
};

export function UserProfile({ userId, onUpdate }: UserProfileProps) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchUser(userId).then(setUser).finally(() => setLoading(false));
  }, [userId]);

  if (loading) return <Skeleton />;
  if (!user) return <ErrorMessage />;

  return (
    <div>
      <h1>{user.name}</h1>
      <p>{user.email}</p>
    </div>
  );
}
```

### 4.2 Custom Hooks
```typescript
// useUser.ts
import { useState, useEffect } from 'react';
import type { User } from '@myworld/types';

export function useUser(userId: number) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchUser(userId)
      .then(data => { if (!cancelled) setUser(data); })
      .catch(err => { if (!cancelled) setError(err); })
      .finally(() => { if (!cancelled) setLoading(false); });
    
    return () => { cancelled = true; };
  }, [userId]);

  return { user, loading, error };
}
```

### 4.3 State Management
- **Local state:** `useState`, `useReducer`
- **Shared state:** Context API (small apps) or Zustand/Jotai (medium apps)
- **Server state:** TanStack Query / SWR
- **Form state:** react-hook-form
- **URL state:** nuqs or useSearchParams

### 4.4 Performance
```tsx
// Memoize expensive components
import { memo } from 'react';

export const TodoList = memo(function TodoList({ todos }: { todos: Todo[] }) {
  return <ul>{todos.map(todo => <TodoItem key={todo.id} todo={todo} />)}</ul>;
});

// Memoize expensive computations
import { useMemo } from 'react';

function FilteredList({ items, query }: Props) {
  const filtered = useMemo(
    () => items.filter(item => item.name.includes(query)),
    [items, query]
  );
  return <List items={filtered} />;
}

// Use stable callbacks
import { useCallback } from 'react';

function Parent() {
  const handleClick = useCallback((id: number) => {
    // handle click
  }, []);
  return <Child onClick={handleClick} />;
}
```

### 4.5 Error Boundaries
```tsx
import { Component, type ReactNode } from 'react';

type Props = { children: ReactNode; fallback?: ReactNode };
type State = { hasError: boolean };

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };
  
  static getDerivedStateFromError(): State {
    return { hasError: true };
  }
  
  componentDidCatch(error: Error, info: { componentStack: string }) {
    console.error('Error caught:', error, info);
  }
  
  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? <ErrorMessage />;
    }
    return this.props.children;
  }
}
```

---

## 5. Forms

### 5.1 Use react-hook-form + Zod
```tsx
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

const schema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
  name: z.string().min(1).max(100),
});

type FormData = z.infer<typeof schema>;

export function SignupForm() {
  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  const onSubmit = (data: FormData) => {
    // submit
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <input {...register('email')} />
      {errors.email && <span>{errors.email.message}</span>}
      <button type="submit">Sign Up</button>
    </form>
  );
}
```

---

## 6. Async / Data Fetching

### 6.1 Use TanStack Query
```tsx
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

export function useTodos() {
  return useQuery({
    queryKey: ['todos'],
    queryFn: () => api.get<Todo[]>('/api/v1/todos'),
  });
}

export function useCreateTodo() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: TodoCreate) => api.post<Todo>('/api/v1/todos', data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['todos'] }),
  });
}
```

### 6.2 Loading & Error States
```tsx
function TodoList() {
  const { data: todos, isLoading, error } = useTodos();

  if (isLoading) return <Skeleton />;
  if (error) return <ErrorMessage error={error} />;
  if (!todos?.length) return <EmptyState />;

  return <ul>{todos.map(todo => <TodoItem key={todo.id} todo={todo} />)}</ul>;
}
```

---

## 7. Accessibility (WCAG 2.1 AA)

### 7.1 Semantic HTML
```tsx
// Good
<button onClick={handleClick}>Click me</button>
<nav><ul><li><a href="/">Home</a></li></ul></nav>

// Bad
<div onClick={handleClick}>Click me</div>
<div><div><div><a href="/">Home</a></div></div></div>
```

### 7.2 ARIA Labels
```tsx
<button aria-label="Close dialog" onClick={onClose}>
  <XIcon />
</button>

<input
  type="text"
  aria-label="Search todos"
  aria-describedby="search-help"
  placeholder="Search..."
/>
```

### 7.3 Keyboard Navigation
- All interactive elements must be keyboard accessible
- Use `tabIndex={0}` for custom interactive elements
- Handle Enter and Space for custom buttons
- Use focus management for modals

### 7.4 Color Contrast
- Text: 4.5:1 (AA) or 7:1 (AAA)
- Large text: 3:1 (AA)
- UI components: 3:1 (AA)

### 7.5 Screen Reader Support
- Use `aria-live="polite"` for dynamic content
- Use `sr-only` class for screen-reader-only text
- Test with actual screen readers

---

## 8. Styling

### 8.1 Tailwind CSS (Primary)
```tsx
// Good: utility classes
<button className="rounded-md bg-blue-600 px-4 py-2 text-white hover:bg-blue-700">
  Save
</button>

// Avoid: inline styles (except dynamic values)
<button style={{ backgroundColor: 'blue' }}>Save</button>
```

### 8.2 Use Design Tokens
```tsx
// Good: design tokens via tailwind config
<div className="bg-primary text-primary-foreground p-md rounded-md">

// Bad: hardcoded values
<div className="bg-[#3b82f6] text-white p-[16px] rounded-[8px]">
```

### 8.3 Component Variants (CVA)
```tsx
import { cva, type VariantProps } from 'class-variance-authority';

const button = cva('rounded-md font-medium', {
  variants: {
    variant: {
      primary: 'bg-blue-600 text-white',
      secondary: 'bg-gray-200 text-gray-900',
      ghost: 'bg-transparent hover:bg-gray-100',
    },
    size: {
      sm: 'px-2 py-1 text-sm',
      md: 'px-4 py-2 text-base',
      lg: 'px-6 py-3 text-lg',
    },
  },
  defaultVariants: { variant: 'primary', size: 'md' },
});

type ButtonProps = VariantProps<typeof button>;

export function Button({ variant, size, ...props }: ButtonProps) {
  return <button className={button({ variant, size })} {...props} />;
}
```

---

## 9. Testing

### 9.1 Component Tests (React Testing Library)
```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

describe('UserProfile', () => {
  it('displays user name', () => {
    render(<UserProfile userId={1} />);
    expect(screen.getByRole('heading')).toHaveTextContent('John Doe');
  });

  it('calls onUpdate when edited', async () => {
    const onUpdate = vi.fn();
    render(<UserProfile userId={1} onUpdate={onUpdate} />);
    await userEvent.click(screen.getByRole('button', { name: /edit/i }));
    expect(onUpdate).toHaveBeenCalled();
  });
});
```

### 9.2 E2E Tests (Playwright)
```ts
import { test, expect } from '@playwright/test';

test('user can create a todo', async ({ page }) => {
  await page.goto('/todos');
  await page.getByRole('button', { name: /new todo/i }).click();
  await page.getByLabel(/title/i).fill('Buy groceries');
  await page.getByRole('button', { name: /save/i }).click();
  await expect(page.getByText('Buy groceries')).toBeVisible();
});
```

---

## 10. Folder Structure

### 10.1 Next.js App (App Router)
```
apps/web/src/
├── app/                    # Routes
│   ├── layout.tsx
│   ├── page.tsx
│   ├── (auth)/
│   │   ├── login/page.tsx
│   │   └── signup/page.tsx
│   ├── api/                # API routes (or external API)
│   └── todos/
│       ├── page.tsx
│       └── [id]/page.tsx
├── components/             # Shared components
│   ├── ui/                 # Design system
│   ├── forms/              # Form components
│   └── features/           # Feature-specific
├── hooks/                  # Custom hooks
├── lib/                    # Utilities
├── types/                  # Type definitions
└── styles/                 # Global styles
```

### 10.2 Feature-First Organization
```
src/features/
├── auth/
│   ├── components/
│   ├── hooks/
│   ├── services/
│   ├── types.ts
│   └── index.ts
├── todos/
│   ├── components/
│   ├── hooks/
│   ├── services/
│   ├── types.ts
│   └── index.ts
```

---

## 11. Anti-Patterns to Avoid

| Anti-Pattern | Why | Instead |
|---|---|---|
| `any` type | Defeats TypeScript | `unknown` + type guard |
| `useEffect` for data fetching | Race conditions, no caching | TanStack Query / SWR |
| Inline object/array in deps | Re-renders every time | `useMemo` or extract |
| Mutating state directly | Breaks React | Use setter or reducer |
| Props drilling | Hard to maintain | Context or state management |
| Index as key | Breaks reconciliation | Stable unique ID |
| `dangerouslySetInnerHTML` | XSS vulnerability | Sanitize or use safe alternative |
| `<div onClick>` | Not accessible | `<button>` or proper role |
| Fetching in component body | Side effects in render | `useEffect` or query |
| `console.log` in production | Performance, noise | Use proper logging |
| Magic strings/numbers | Hard to maintain | Constants or enums |
| `==` | Type coercion | `===` and `!==` |
| Missing `key` prop | React warnings | Always provide unique key |
| Synchronous setState in render | Infinite loop | `useEffect` or event handler |

---

## 12. References

- [Google TypeScript Style Guide](https://google.github.io/styleguide/tsguide.html)
- [Airbnb React Style Guide](https://github.com/airbnb/javascript/tree/master/react)
- [React Official Docs](https://react.dev/)
- [Next.js App Router](https://nextjs.org/docs/app)
- [WCAG 2.1 AA](https://www.w3.org/WAI/WCAG21/quickref/?versions=2.1&levels=aa)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/handbook/intro.html)
- [TanStack Query](https://tanstack.com/query/latest)
- [Zod](https://zod.dev/)

---

## 13. Enforcement

These standards are enforced by:
- **TypeScript Compiler** (`tsc --noEmit`)
- **ESLint** (when added to project)
- **Prettier** (when added to project)
- **Code review** — Standards not caught by tools
- **Pre-commit hooks** — Local enforcement
