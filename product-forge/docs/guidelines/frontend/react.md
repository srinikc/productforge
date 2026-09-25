# Frontend Engineering Standards

> React 19, Next.js 15, and modern web frontend patterns for MyWorld Central Portal.

## Table of Contents

1. [Component Architecture](#component-architecture)
2. [React 19 Patterns](#react-19-patterns)
3. [Next.js 15 App Router](#nextjs-15-app-router)
4. [State Management](#state-management)
5. [Data Fetching](#data-fetching)
6. [Forms and Validation](#forms-and-validation)
7. [Routing and Navigation](#routing-and-navigation)
8. [Performance Optimization](#performance-optimization)
9. [Server Components vs Client Components](#server-components-vs-client-components)
10. [Error Handling](#error-handling)
11. [Testing](#testing)
12. [Accessibility Integration](#accessibility-integration)

---

## Component Architecture

### Component Hierarchy

```
src/
├── app/                    # Next.js App Router (pages, layouts, routes)
│   ├── (auth)/            # Route groups for auth-required pages
│   ├── (public)/          # Route groups for public pages
│   ├── api/               # API route handlers
│   ├── layout.tsx         # Root layout
│   ├── page.tsx           # Home page
│   └── globals.css
├── components/            # Reusable UI components
│   ├── ui/                # Primitive UI components (Button, Input, etc.)
│   ├── features/          # Feature-specific components
│   └── layouts/           # Layout components
├── lib/                   # Utility libraries, third-party clients
├── hooks/                 # Custom React hooks
├── stores/                # State management (Zustand, Jotai)
├── types/                 # TypeScript type definitions
└── styles/                # Global styles, theme config
```

### Component Naming

```typescript
// GOOD: Descriptive, PascalCase, suffix indicates type
UserProfileCard.tsx           // Feature component
ProductListItem.tsx           // List item
CheckoutForm.tsx              // Form
useAuth.ts                    // Hook
apiClient.ts                  // API client
Button.tsx                    // UI primitive
Avatar.tsx                    // UI primitive
```

### Component File Structure

```typescript
// 1. Imports (external, then internal, then types, then styles)
// 2. Types/interfaces
// 3. Constants
// 4. Main component (default export for pages, named for components)
// 5. Sub-components (private to file)
// 6. Helper functions
// 7. Default export
```

**Rule:** One component per file. Co-locate sub-components in same file only if they are not used elsewhere.

### Props Interface

```typescript
// GOOD: Explicit interface, JSDoc for complex props
interface UserCardProps {
  /** User ID to display */
  userId: string;
  /** Whether to show the user's email */
  showEmail?: boolean;
  /** Callback when the card is clicked */
  onClick?: (userId: string) => void;
  /** Card variant for different contexts */
  variant?: 'compact' | 'detailed';
}

export function UserCard({ 
  userId, 
  showEmail = false, 
  onClick,
  variant = 'detailed' 
}: UserCardProps) {
  // ...
}
```

**Rules:**
- Always define an interface for props (don't use `any` or inline types)
- Required props first, optional props with defaults
- Use `interface` for object types, `type` for unions/intersections
- Document non-obvious props with JSDoc
- Extend HTML element props when wrapping native elements: `extends HTMLAttributes<HTMLDivElement>`

---

## React 19 Patterns

### Server Components by Default

```typescript
// GOOD: Server Component (default in App Router)
// No 'use client' directive needed
import { getUser } from '@/lib/api';

export default async function UserPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const user = await getUser(id);
  return <UserCard user={user} />;
}
```

```typescript
// GOOD: Client Component (when you need interactivity)
// 'use client' at the top
'use client';

import { useState } from 'react';

export function Counter() {
  const [count, setCount] = useState(0);
  return <button onClick={() => setCount(c => c + 1)}>{count}</button>;
}
```

**Rule:** Start with Server Components. Add `'use client'` only when you need:
- Event handlers (`onClick`, `onChange`)
- Browser APIs (`window`, `localStorage`)
- State (`useState`, `useReducer`)
- Effects (`useEffect`)
- Custom hooks that use the above

### React 19 New APIs

```typescript
// GOOD: use() hook for promises and context
import { use, Suspense } from 'react';

function UserProfile({ userPromise }: { userPromise: Promise<User> }) {
  const user = use(userPromise);  // Suspends until resolved
  return <div>{user.name}</div>;
}

// GOOD: useOptimistic for instant UI feedback
'use client';
import { useOptimistic } from 'react';

function LikeButton({ postId, initialLikes }: Props) {
  const [optimisticLikes, addOptimisticLike] = useOptimistic(
    initialLikes,
    (state, amount: number) => state + amount
  );
  
  async function handleLike() {
    addOptimisticLike(1);
    await likePost(postId);
  }
  
  return <button onClick={handleLike}>{optimisticLikes}</button>;
}

// GOOD: useActionState for form actions
'use client';
import { useActionState } from 'react';

function ContactForm() {
  const [state, formAction, isPending] = useActionState(
    submitContact,
    { errors: null, success: false }
  );
  
  return (
    <form action={formAction}>
      {/* ... */}
      <button disabled={isPending}>Submit</button>
    </form>
  );
}

// GOOD: Server Actions with 'use server'
'use server';

export async function submitContact(prevState: State, formData: FormData) {
  // Validate and process
  return { errors: null, success: true };
}
```

### Refs (React 19)

```typescript
// GOOD: ref as a regular prop (no forwardRef needed in React 19)
function MyInput({ ref, ...props }: { ref?: Ref<HTMLInputElement> } & InputProps) {
  return <input ref={ref} {...props} />;
}

// GOOD: use ref callback for cleanup
function Tooltip({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    
    const observer = new ResizeObserver(() => { /* ... */ });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  
  return <div ref={ref}>{children}</div>;
}
```

### Hooks Rules

```typescript
// GOOD: Custom hook with clear naming
function useUser(userId: string) {
  return useQuery({
    queryKey: ['user', userId],
    queryFn: () => getUser(userId),
  });
}

// GOOD: Compose hooks
function useCurrentUserWithPosts() {
  const user = useUser('me');
  const posts = usePosts(user.data?.id);
  return { user, posts };
}

// BAD: Conditional hooks (violates Rules of Hooks)
function BadComponent({ shouldFetch }: { shouldFetch: boolean }) {
  if (shouldFetch) {
    const data = useFetch('/api/data');  // ❌ NEVER DO THIS
  }
}

// GOOD: Always call hooks at the top level
function GoodComponent({ shouldFetch }: { shouldFetch: boolean }) {
  const { data } = useFetch('/api/data', { enabled: shouldFetch });
}
```

---

## Next.js 15 App Router

### File Conventions

```
app/
├── layout.tsx           # Root layout (required)
├── page.tsx             # Home page (/)
├── loading.tsx          # Loading UI for Suspense
├── error.tsx            # Error UI ('use client' required)
├── not-found.tsx        # 404 UI
├── global-error.tsx     # Global error UI
├── route.ts             # API route handler
├── template.tsx         # Re-rendered layout
└── default.tsx          # Parallel route default
```

### Layout Pattern

```typescript
// GOOD: Root layout with metadata
import type { Metadata } from 'next';
import { Inter } from 'next/font/google';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: {
    default: 'MyWorld',
    template: '%s | MyWorld',
  },
  description: 'Central portal for MyWorld services',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
```

### Page Component

```typescript
// GOOD: Async page component with params as Promise
type Params = Promise<{ id: string }>;
type SearchParams = Promise<{ [key: string]: string | string[] | undefined }>;

export default async function ProductPage({
  params,
  searchParams,
}: {
  params: Params;
  searchParams: SearchParams;
}) {
  const { id } = await params;
  const { sort } = await searchParams;
  
  const product = await getProduct(id);
  if (!product) notFound();
  
  return <ProductDetail product={product} />;
}

// GOOD: Generate metadata
export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { id } = await params;
  const product = await getProduct(id);
  return {
    title: product?.name,
    description: product?.description,
  };
}

// GOOD: Generate static params
export async function generateStaticParams() {
  const products = await getTopProducts(100);
  return products.map(p => ({ id: p.id }));
}
```

### Server Actions

```typescript
// GOOD: Server action for form submission
'use server';

import { revalidatePath } from 'next/cache';
import { z } from 'zod';

const updateProfileSchema = z.object({
  name: z.string().min(1).max(100),
  bio: z.string().max(500).optional(),
});

export async function updateProfile(userId: string, formData: FormData) {
  const validated = updateProfileSchema.parse({
    name: formData.get('name'),
    bio: formData.get('bio'),
  });
  
  await db.user.update({ where: { id: userId }, data: validated });
  revalidatePath(`/profile/${userId}`);
}

// GOOD: With auth check
export async function deletePost(postId: string) {
  const session = await auth();
  if (!session?.user) throw new Error('Unauthorized');
  
  const post = await db.post.findUnique({ where: { id: postId } });
  if (post?.authorId !== session.user.id) throw new Error('Forbidden');
  
  await db.post.delete({ where: { id: postId } });
  revalidatePath('/posts');
}
```

### Route Handlers (API Routes)

```typescript
// GOOD: API route with validation
import { NextRequest, NextResponse } from 'next/server';
import { z } from 'zod';

const createUserSchema = z.object({
  email: z.string().email(),
  name: z.string().min(1),
});

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const data = createUserSchema.parse(body);
    const user = await createUser(data);
    return NextResponse.json(user, { status: 201 });
  } catch (error) {
    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { error: 'Validation failed', details: error.errors },
        { status: 400 }
      );
    }
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

// GOOD: Dynamic route params
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const user = await getUser(id);
  if (!user) return NextResponse.json({ error: 'Not found' }, { status: 404 });
  return NextResponse.json(user);
}
```

### Middleware

```typescript
// middleware.ts (at project root)
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  // Auth check
  const token = request.cookies.get('session')?.value;
  
  if (request.nextUrl.pathname.startsWith('/dashboard') && !token) {
    return NextResponse.redirect(new URL('/login', request.url));
  }
  
  // Add custom header
  const response = NextResponse.next();
  response.headers.set('x-custom-header', 'value');
  return response;
}

export const config = {
  matcher: ['/dashboard/:path*', '/api/:path*'],
};
```

---

## State Management

### Server State (TanStack Query)

```typescript
// GOOD: Query hook with proper typing
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

export function useUser(userId: string) {
  return useQuery({
    queryKey: ['user', userId],
    queryFn: () => api.get<User>(`/users/${userId}`),
    staleTime: 5 * 60 * 1000,  // 5 minutes
    gcTime: 10 * 60 * 1000,   // 10 minutes (formerly cacheTime)
    enabled: !!userId,
  });
}

// GOOD: Mutation with optimistic update
export function useUpdateUser() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: UpdateUserInput) => api.put<User>('/users/me', data),
    onMutate: async (newData) => {
      await queryClient.cancelQueries({ queryKey: ['user', 'me'] });
      const previous = queryClient.getQueryData<User>(['user', 'me']);
      
      queryClient.setQueryData<User>(['user', 'me'], (old) => 
        old ? { ...old, ...newData } : old
      );
      
      return { previous };
    },
    onError: (err, newData, context) => {
      if (context?.previous) {
        queryClient.setQueryData(['user', 'me'], context.previous);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['user', 'me'] });
    },
  });
}
```

### Client State (Zustand)

```typescript
// GOOD: Zustand store with TypeScript
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UIState {
  sidebarOpen: boolean;
  theme: 'light' | 'dark';
  toggleSidebar: () => void;
  setTheme: (theme: 'light' | 'dark') => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      sidebarOpen: false,
      theme: 'light',
      toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
      setTheme: (theme) => set({ theme }),
    }),
    {
      name: 'ui-storage',
      partialize: (state) => ({ theme: state.theme }),  // Only persist theme
    }
  )
);

// GOOD: Selector pattern to avoid re-renders
function Sidebar() {
  const sidebarOpen = useUIStore((s) => s.sidebarOpen);  // Only re-renders on this
  return sidebarOpen ? <SidebarContent /> : null;
}

// BAD: Subscribing to entire store (causes re-renders on any change)
function BadSidebar() {
  const state = useUIStore();  // ❌ Re-renders on ANY change
  return state.sidebarOpen ? <SidebarContent /> : null;
}
```

### URL State

```typescript
// GOOD: Use search params for shareable state
'use client';
import { useSearchParams, useRouter } from 'next/navigation';

function ProductFilters() {
  const searchParams = useSearchParams();
  const router = useRouter();
  
  const category = searchParams.get('category') ?? 'all';
  
  function setCategory(newCategory: string) {
    const params = new URLSearchParams(searchParams);
    params.set('category', newCategory);
    router.push(`?${params.toString()}`);
  }
  
  return <CategoryFilter value={category} onChange={setCategory} />;
}
```

### Form State (React Hook Form)

```typescript
// GOOD: Form with validation
'use client';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

const schema = z.object({
  email: z.string().email('Invalid email'),
  password: z.string().min(8, 'Min 8 characters'),
});

type FormData = z.infer<typeof schema>;

export function LoginForm() {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
  });
  
  async function onSubmit(data: FormData) {
    await loginUser(data);
  }
  
  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <input {...register('email')} aria-invalid={!!errors.email} />
      {errors.email && <span role="alert">{errors.email.message}</span>}
      
      <input type="password" {...register('password')} aria-invalid={!!errors.password} />
      {errors.password && <span role="alert">{errors.password.message}</span>}
      
      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Logging in...' : 'Log in'}
      </button>
    </form>
  );
}
```

---

## Data Fetching

### Server-Side Fetching (RSC)

```typescript
// GOOD: Fetch in Server Component
async function getProducts(): Promise<Product[]> {
  const res = await fetch('https://api.example.com/products', {
    next: { revalidate: 3600 },  // ISR: revalidate every hour
  });
  if (!res.ok) throw new Error('Failed to fetch products');
  return res.json();
}

export default async function ProductsPage() {
  const products = await getProducts();
  return <ProductList products={products} />;
}
```

### Client-Side Fetching (SWR/TanStack Query)

```typescript
// GOOD: Prefetch on server, hydrate on client
import { HydrationBoundary, dehydrate, QueryClient } from '@tanstack/react-query';

export default async function ProductsPage() {
  const queryClient = new QueryClient();
  
  await queryClient.prefetchQuery({
    queryKey: ['products'],
    queryFn: () => api.get<Product[]>('/products'),
  });
  
  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <ProductList />
    </HydrationBoundary>
  );
}
```

### Error Handling for Fetch

```typescript
// GOOD: Typed error handling
class APIError extends Error {
  constructor(
    message: string,
    public status: number,
    public code?: string,
  ) {
    super(message);
    this.name = 'APIError';
  }
}

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new APIError(
      error.message ?? 'Request failed',
      res.status,
      error.code,
    );
  }
  return res.json();
}
```

---

## Forms and Validation

### Form Best Practices

```typescript
// GOOD: Accessible form with proper labels and validation
'use client';
import { useId } from 'react';

export function SignupForm() {
  const nameId = useId();
  const emailId = useId();
  const errorId = useId();
  
  return (
    <form noValidate>
      <div>
        <label htmlFor={nameId}>Name <span aria-label="required">*</span></label>
        <input
          id={nameId}
          name="name"
          required
          aria-required="true"
          aria-invalid={!!errors.name}
          aria-describedby={errors.name ? errorId : undefined}
        />
        {errors.name && <p id={errorId} role="alert">{errors.name}</p>}
      </div>
      
      <button type="submit">Sign up</button>
    </form>
  );
}
```

### Schema Validation

```typescript
// GOOD: Reusable Zod schema
import { z } from 'zod';

export const userSchema = z.object({
  email: z.string().email().toLowerCase().trim(),
  password: z
    .string()
    .min(8, 'Password must be at least 8 characters')
    .regex(/[A-Z]/, 'Must contain uppercase letter')
    .regex(/[0-9]/, 'Must contain number'),
  name: z.string().min(1).max(100).trim(),
  age: z.number().int().min(13).max(120).optional(),
});

export type UserInput = z.infer<typeof userSchema>;
```

---

## Routing and Navigation

### Link Component

```typescript
// GOOD: Use Link for internal navigation
import Link from 'next/link';

export function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
  return <Link href={href}>{children}</Link>;
}

// GOOD: Active link with usePathname
'use client';
import { usePathname } from 'next/navigation';

function NavItem({ href, children }: Props) {
  const pathname = usePathname();
  const isActive = pathname === href;
  
  return (
    <Link 
      href={href} 
      aria-current={isActive ? 'page' : undefined}
      className={isActive ? 'active' : ''}
    >
      {children}
    </Link>
  );
}

// BAD: Using <a> for internal links (causes full page reload)
function BadNavItem() {
  return <a href="/about">About</a>;  // ❌
}
```

### Programmatic Navigation

```typescript
// GOOD: Use router.push for navigation
'use client';
import { useRouter } from 'next/navigation';

function LoginForm() {
  const router = useRouter();
  
  async function onSubmit(data: FormData) {
    const result = await login(data);
    if (result.success) {
      router.push('/dashboard');
      router.refresh();  // Refresh server data
    }
  }
}
```

---

## Performance Optimization

### Code Splitting

```typescript
// GOOD: Dynamic import for heavy components
import dynamic from 'next/dynamic';

const HeavyChart = dynamic(() => import('./HeavyChart'), {
  loading: () => <ChartSkeleton />,
  ssr: false,  // Client-only
});

// GOOD: Named export for dynamic import
const Editor = dynamic(
  () => import('./Editor').then(mod => mod.Editor),
  { ssr: false }
);
```

### Image Optimization

```typescript
// GOOD: Use next/image
import Image from 'next/image';

<Image
  src="/hero.jpg"
  alt="Hero image"
  width={1200}
  height={600}
  priority  // For above-the-fold images
  placeholder="blur"
  blurDataURL={blurDataUrl}
/>

// GOOD: Responsive images
<Image
  src="/product.jpg"
  alt={product.name}
  fill
  sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
  style={{ objectFit: 'cover' }}
/>
```

### Font Optimization

```typescript
// GOOD: Use next/font
import { Inter, Roboto_Mono } from 'next/font/google';

const inter = Inter({ 
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-inter',
});

const robotoMono = Roboto_Mono({ 
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-roboto-mono',
});

// In layout
<html className={`${inter.variable} ${robotoMono.variable}`}>
```

### Memoization

```typescript
// GOOD: useMemo for expensive calculations
function ProductList({ products, filter }: Props) {
  const filteredProducts = useMemo(
    () => products.filter(p => p.category === filter),
    [products, filter]
  );
  
  return <List items={filteredProducts} />;
}

// GOOD: useCallback for stable function references
function Parent() {
  const [count, setCount] = useState(0);
  
  const handleClick = useCallback(() => {
    setCount(c => c + 1);
  }, []);  // Stable reference
  
  return <Child onClick={handleClick} />;
}

// GOOD: React.memo for pure components
const ProductCard = memo(function ProductCard({ product }: Props) {
  return <div>{product.name}</div>;
});

// BAD: Over-memoization (premature optimization)
function SimpleComponent({ name }: { name: string }) {
  const upperName = useMemo(() => name.toUpperCase(), [name]);  // ❌ Overkill
  return <div>{upperName}</div>;
}
```

### Bundle Analysis

```typescript
// next.config.js
const withBundleAnalyzer = require('@next/bundle-analyzer')({
  enabled: process.env.ANALYZE === 'true',
});

module.exports = withBundleAnalyzer({
  // config
});
```

```bash
# Run analyzer
ANALYZE=true pnpm build
```

---

## Server Components vs Client Components

### Decision Tree

```
Does it need interactivity or browser APIs?
├── NO → Server Component (default)
│   ├── Fetches data
│   ├── Renders static content
│   └── Composes layout
└── YES → Client Component ('use client')
    ├── Has onClick, onChange, etc.
    ├── Uses useState, useEffect
    └── Accesses browser APIs
```

### Composition Pattern

```typescript
// GOOD: Server Component imports Client Component
// app/dashboard/page.tsx (Server)
import { DashboardClient } from './dashboard-client';

export default async function DashboardPage() {
  const data = await fetchDashboardData();
  return <DashboardClient initialData={data} />;
}

// app/dashboard/dashboard-client.tsx ('use client')
'use client';
export function DashboardClient({ initialData }: Props) {
  const [filter, setFilter] = useState('');
  // Interactive logic here
  return <InteractiveDashboard data={initialData} filter={filter} />;
}
```

### Pass Server Data to Client

```typescript
// GOOD: Serialize data before passing to client components
export default async function Page() {
  const products = await getProducts();
  return <ProductGrid products={products} />;  // products must be serializable
}

// BAD: Passing non-serializable data
export default async function Page() {
  const db = getDB();  // ❌ Cannot pass DB connection to client
  return <ClientComponent db={db} />;
}
```

---

## Error Handling

### Error Boundaries

```typescript
// GOOD: Error boundary for route segment
'use client';
import { useEffect } from 'react';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log to error reporting service
    console.error(error);
  }, [error]);
  
  return (
    <div>
      <h2>Something went wrong!</h2>
      <button onClick={() => reset()}>Try again</button>
    </div>
  );
}

// GOOD: Custom error boundary component
'use client';
import { Component, ReactNode } from 'react';

interface Props { children: ReactNode; fallback: ReactNode; }
interface State { hasError: boolean; }

class ErrorBoundary extends Component<Props, State> {
  state = { hasError: false };
  
  static getDerivedStateFromError() {
    return { hasError: true };
  }
  
  componentDidCatch(error: Error, info: { componentStack: string }) {
    console.error('Error caught:', error, info);
  }
  
  render() {
    if (this.state.hasError) return this.props.fallback;
    return this.props.children;
  }
}
```

### Loading States

```typescript
// GOOD: Suspense boundary with skeleton
import { Suspense } from 'react';

export default function Page() {
  return (
    <Suspense fallback={<ProductListSkeleton />}>
      <ProductList />
    </Suspense>
  );
}

// GOOD: Loading UI (loading.tsx)
export default function Loading() {
  return <ProductListSkeleton />;
}
```

### Not Found

```typescript
// GOOD: notFound() for missing resources
import { notFound } from 'next/navigation';

export default async function ProductPage({ params }: Props) {
  const { id } = await params;
  const product = await getProduct(id);
  
  if (!product) notFound();  // Renders not-found.tsx
  return <ProductDetail product={product} />;
}

// not-found.tsx
export default function NotFound() {
  return (
    <div>
      <h2>Not Found</h2>
      <p>Could not find the requested resource.</p>
    </div>
  );
}
```

---

## Testing

### Component Testing (Vitest + Testing Library)

```typescript
// GOOD: Test user behavior, not implementation
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { LoginForm } from './login-form';

describe('LoginForm', () => {
  it('submits form with user credentials', async () => {
    const onSubmit = vi.fn();
    render(<LoginForm onSubmit={onSubmit} />);
    
    await userEvent.type(screen.getByLabelText(/email/i), 'user@example.com');
    await userEvent.type(screen.getByLabelText(/password/i), 'password123');
    await userEvent.click(screen.getByRole('button', { name: /log in/i }));
    
    expect(onSubmit).toHaveBeenCalledWith({
      email: 'user@example.com',
      password: 'password123',
    });
  });
  
  it('displays validation errors', async () => {
    render(<LoginForm onSubmit={vi.fn()} />);
    
    await userEvent.click(screen.getByRole('button', { name: /log in/i }));
    
    expect(await screen.findByText(/email is required/i)).toBeInTheDocument();
  });
});
```

### E2E Testing (Playwright)

```typescript
// GOOD: E2E test with stable locators
import { test, expect } from '@playwright/test';

test('user can complete checkout', async ({ page }) => {
  await page.goto('/products');
  await page.getByRole('link', { name: 'Product A' }).click();
  await page.getByRole('button', { name: 'Add to cart' }).click();
  await page.getByRole('link', { name: 'Cart' }).click();
  await page.getByRole('button', { name: 'Checkout' }).click();
  
  await expect(page.getByRole('heading', { name: 'Order Confirmation' })).toBeVisible();
});
```

---

## Accessibility Integration

### Semantic HTML First

```typescript
// GOOD: Semantic elements
<header>
  <nav>
    <ul>
      <li><a href="/">Home</a></li>
    </ul>
  </nav>
</header>

<main>
  <article>
    <h1>Title</h1>
    <p>Content</p>
  </article>
</main>

<footer>© 2026</footer>

// BAD: Divs for everything
<div className="header">
  <div className="nav">
    <div className="link">Home</div>  // ❌ Not focusable, not announced
  </div>
</div>
```

### ARIA When Needed

```typescript
// GOOD: Use ARIA only when semantic HTML isn't enough
<button aria-expanded={isOpen} aria-controls="menu">
  Menu
</button>
<ul id="menu" role="menu" hidden={!isOpen}>
  <li role="menuitem">Item 1</li>
</ul>

// GOOD: Live region for dynamic updates
<div aria-live="polite" aria-atomic="true">
  {statusMessage}
</div>
```

### Focus Management

```typescript
// GOOD: Manage focus on modal open/close
function Modal({ isOpen, onClose, children }: Props) {
  const modalRef = useRef<HTMLDivElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  
  useEffect(() => {
    if (isOpen) {
      previousFocus.current = document.activeElement as HTMLElement;
      modalRef.current?.focus();
      return () => previousFocus.current?.focus();
    }
  }, [isOpen]);
  
  if (!isOpen) return null;
  
  return (
    <div role="dialog" aria-modal="true" ref={modalRef} tabIndex={-1}>
      {children}
      <button onClick={onClose}>Close</button>
    </div>
  );
}
```

---

## Best Practices Summary

| ✅ DO | ❌ DON'T |
|---|---|
| Server Components by default | Use Client Components unnecessarily |
| Semantic HTML first | Use divs for everything |
| Use `useId()` for accessible IDs | Use array indices or random IDs |
| Validate forms with Zod | Trust client-side validation alone |
| Use `next/image` for images | Use raw `<img>` tags |
| Use `next/font` for fonts | Import fonts via CSS |
| Use `next/link` for internal navigation | Use `<a>` for internal links |
| Use Server Actions for mutations | Create API routes unnecessarily |
| Co-locate related files | Deep folder hierarchies |
| Test user behavior | Test implementation details |
| Use `useOptimistic` for instant feedback | Show loading spinners unnecessarily |
| Use TanStack Query for client state caching | Re-fetch data on every render |
| Use `useTransition` for non-urgent updates | Block UI for slow operations |

---

## References

- [React 19 Documentation](https://react.dev)
- [Next.js 15 Documentation](https://nextjs.org/docs)
- [TanStack Query](https://tanstack.com/query)
- [Zustand](https://zustand-demo.pmnd.rs/)
- [React Hook Form](https://react-hook-form.com/)
- [Zod](https://zod.dev/)
- [WCAG 2.1 AA](https://www.w3.org/WAI/WCAG21/quickref/)
- [Testing Library](https://testing-library.com/docs/react-testing-library/intro/)
- [Playwright](https://playwright.dev/)
