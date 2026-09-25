# Rendering Engineering Standards

> Server-side rendering, static generation, and client-side rendering strategies for MyWorld Central Portal.

## Table of Contents

1. [Rendering Strategies](#rendering-strategies)
2. [When to Use Each Strategy](#when-to-use-each-strategy)
3. [Next.js Rendering Patterns](#nextjs-rendering-patterns)
4. [Static Site Generation (SSG)](#static-site-generation-ssg)
5. [Server-Side Rendering (SSR)](#server-side-rendering-ssr)
6. [Incremental Static Regeneration (ISR)](#incremental-static-regeneration-isr)
7. [Client-Side Rendering (CSR)](#client-side-rendering-csr)
8. [Streaming and Suspense](#streaming-and-suspense)
9. [Edge Rendering](#edge-rendering)
10. [SEO Considerations](#seo-considerations)

---

## Rendering Strategies

### Overview

| Strategy | When to Use | Pros | Cons |
|----------|-------------|------|------|
| **SSG** | Static content | Fastest, cached at edge | Stale data, slow rebuilds |
| **ISR** | Static + occasional updates | Fast + fresh | Revalidation complexity |
| **SSR** | Dynamic, per-user content | Always fresh | Slower, server load |
| **CSR** | Heavy interactivity | Rich interactions | Slow first paint, poor SEO |
| **RSC** | Server data + client interactivity | Best of both | Newer, learning curve |
| **Edge** | Geo-distributed logic | Low latency | Limited runtime |

---

## When to Use Each Strategy

### Decision Tree

```
Is the page static (same for all users)?
├── YES → Does it change frequently?
│   ├── NO → Use SSG
│   └── YES → Use ISR (with revalidation)
└── NO → Is the data user-specific?
    ├── YES → SSR with user session
    └── NO → SSR or RSC with shared data
```

### Examples in MyWorld

| Page | Strategy | Reason |
|------|----------|--------|
| Landing page | SSG/ISR | Marketing content, occasional updates |
| Pricing | SSG | Static, rarely changes |
| Blog post | SSG + ISR | Static, updated occasionally |
| Dashboard | RSC | User-specific, real-time data |
| User profile (own) | RSC | User-specific |
| User profile (others) | SSR | Public, but personalized |
| Product list | ISR | Semi-static, changes with inventory |
| Product detail | SSR/ISR | Dynamic pricing, stock |
| Search results | CSR | Highly interactive, user-specific |
| Settings | RSC | User-specific, forms |

---

## Next.js Rendering Patterns

### React Server Components (Default in App Router)

```typescript
// GOOD: Server Component (default)
// app/products/page.tsx

import { getProducts } from '@/lib/api';

export default async function ProductsPage({
  searchParams,
}: {
  searchParams: Promise<{ category?: string }>;
}) {
  // Runs on server, never sent to client
  const { category } = await searchParams;
  const products = await getProducts({ category });
  
  return (
    <div>
      <h1>Products</h1>
      <ProductList products={products} />
    </div>
  );
}


// GOOD: Server Component with data fetching
// app/dashboard/page.tsx

import { auth } from '@/lib/auth';
import { getDashboardData } from '@/lib/dashboard';

export default async function DashboardPage() {
  const session = await auth();
  
  if (!session) {
    redirect('/login');
  }
  
  // Server-side data fetching (no client bundle)
  const data = await getDashboardData(session.user.id);
  
  return <DashboardView data={data} />;
}
```

### Client Components

```typescript
// GOOD: Client Component (when needed)
// app/components/interactive-counter.tsx
'use client';

import { useState } from 'react';

export function InteractiveCounter() {
  const [count, setCount] = useState(0);
  
  return (
    <button onClick={() => setCount(c => c + 1)}>
      Count: {count}
    </button>
  );
}


// GOOD: Server Component with Client Component child
// app/profile/page.tsx (Server)
import { ProfileEditor } from './profile-editor';

export default async function ProfilePage() {
  const user = await getUser();
  
  return (
    <div>
      <h1>Profile</h1>
      <ProfileEditor user={user} />  {/* Client child */}
    </div>
  );
}


// app/profile/profile-editor.tsx ('use client')
'use client';

import { useState } from 'react';

export function ProfileEditor({ user }: { user: User }) {
  const [name, setName] = useState(user.name);
  // Interactive form logic
  return <input value={name} onChange={e => setName(e.target.value)} />;
}
```

### Composition Pattern

```typescript
// GOOD: Server Component fetches data, passes to Client
// app/products/[id]/page.tsx (Server)
import { getProduct } from '@/lib/api';
import { ProductInteractive } from './product-interactive';

export default async function ProductPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const product = await getProduct(id);
  
  if (!product) notFound();
  
  return (
    <div>
      {/* Server-rendered static content */}
      <h1>{product.name}</h1>
      <p>{product.description}</p>
      <img src={product.image} alt={product.name} />
      
      {/* Client-side interactive part */}
      <ProductInteractive product={product} />
    </div>
  );
}


// app/products/[id]/product-interactive.tsx ('use client')
'use client';

import { useState } from 'react';

export function ProductInteractive({ product }: { product: Product }) {
  const [quantity, setQuantity] = useState(1);
  const [isAddingToCart, setIsAddingToCart] = useState(false);
  
  async function addToCart() {
    setIsAddingToCart(true);
    await addProductToCart(product.id, quantity);
    setIsAddingToCart(false);
  }
  
  return (
    <div>
      <input
        type="number"
        value={quantity}
        onChange={e => setQuantity(Number(e.target.value))}
      />
      <button onClick={addToCart} disabled={isAddingToCart}>
        {isAddingToCart ? 'Adding...' : 'Add to Cart'}
      </button>
    </div>
  );
}
```

---

## Static Site Generation (SSG)

### When to Use SSG

✅ **Use SSG for:**
- Marketing pages (landing, pricing, about)
- Blog posts
- Documentation
- Terms of service, privacy policy
- Product catalogs (if rarely updated)

### Implementation

```typescript
// app/about/page.tsx
export default function AboutPage() {
  return (
    <div>
      <h1>About MyWorld</h1>
      <p>We are building the future of...</p>
    </div>
  );
}


// GOOD: Pre-render at build time
// app/blog/[slug]/page.tsx

export async function generateStaticParams() {
  // Pre-render these pages at build time
  const posts = await getAllPosts();
  return posts.map(post => ({ slug: post.slug }));
}

export default async function BlogPostPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const post = await getPost(slug);
  
  if (!post) notFound();
  
  return (
    <article>
      <h1>{post.title}</h1>
      <div>{post.content}</div>
    </article>
  );
}


// GOOD: Dynamic metadata for SSG
export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const post = await getPost(slug);
  
  return {
    title: post.title,
    description: post.excerpt,
    openGraph: {
      title: post.title,
      description: post.excerpt,
      images: [post.coverImage],
    },
  };
}
```

### SSG Trade-offs

```markdown
**Pros:**
- Fastest possible load time (served from CDN)
- Cheap to serve (no server computation)
- SEO-friendly (HTML is ready)
- Highly cacheable

**Cons:**
- Stale data (only updated on rebuild)
- Slow updates (requires full rebuild)
- Not suitable for user-specific content
- Large sites have long build times
```

---

## Server-Side Rendering (SSR)

### When to Use SSR

✅ **Use SSR for:**
- User dashboards
- Personalized content
- Real-time data
- Authenticated pages
- Search results (with filters)

### Implementation

```typescript
// GOOD: SSR with dynamic data
// app/dashboard/page.tsx

export const dynamic = 'force-dynamic';  // Always SSR, no caching

export default async function DashboardPage() {
  const session = await auth();
  
  if (!session) {
    redirect('/login');
  }
  
  // Fresh data on every request
  const [user, posts, stats] = await Promise.all([
    getUser(session.user.id),
    getUserPosts(session.user.id),
    getUserStats(session.user.id),
  ]);
  
  return <DashboardView user={user} posts={posts} stats={stats} />;
}


// GOOD: SSR with cache (revalidate every minute)
export const revalidate = 60;  // ISR with 60-second revalidation

export default async function ProductsPage() {
  const products = await getProducts();
  return <ProductList products={products} />;
}


// GOOD: SSR with cache tags (invalidate on demand)
import { unstable_cache } from 'next/cache';

const getProductsCached = unstable_cache(
  async () => getProducts(),
  ['products'],
  { revalidate: 3600, tags: ['products'] }
);

export default async function ProductsPage() {
  const products = await getProductsCached();
  return <ProductList products={products} />;
}
```

### SSR with Streaming

```typescript
// GOOD: Stream slow parts of the page
// app/dashboard/page.tsx

import { Suspense } from 'react';

export default function DashboardPage() {
  return (
    <div>
      <h1>Dashboard</h1>
      
      {/* Fast content renders immediately */}
      <UserInfo />
      
      {/* Slow content streams in */}
      <Suspense fallback={<StatsSkeleton />}>
        <SlowStats />
      </Suspense>
      
      <Suspense fallback={<ActivitySkeleton />}>
        <RecentActivity />
      </Suspense>
    </div>
  );
}


// SlowStats component (Server Component with await)
async function SlowStats() {
  // Simulate slow data fetch
  const stats = await getExpensiveStats();
  return <StatsView stats={stats} />;
}
```

---

## Incremental Static Regeneration (ISR)

### When to Use ISR

✅ **Use ISR for:**
- E-commerce product pages
- News articles
- Social media feeds
- Content that changes occasionally

### Time-Based Revalidation

```typescript
// GOOD: ISR with time-based revalidation
// app/products/[id]/page.tsx

export const revalidate = 3600;  // Revalidate every hour

export default async function ProductPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const product = await getProduct(id);
  
  if (!product) notFound();
  
  return <ProductDetail product={product} />;
}


// GOOD: Pre-generate popular products, ISR for the rest
export async function generateStaticParams() {
  const popularProducts = await getPopularProducts(100);
  return popularProducts.map(p => ({ id: p.id }));
}

// Other products will be generated on-demand
```

### On-Demand Revalidation

```typescript
// app/api/revalidate/route.ts
import { revalidatePath, revalidateTag } from 'next/cache';

export async function POST(request: NextRequest) {
  const secret = request.headers.get('x-revalidate-secret');
  
  if (secret !== process.env.REVALIDATE_SECRET) {
    return NextResponse.json({ message: 'Invalid token' }, { status: 401 });
  }
  
  const body = await request.json();
  
  if (body.path) {
    revalidatePath(body.path);
  }
  
  if (body.tag) {
    revalidateTag(body.tag);
  }
  
  return NextResponse.json({ revalidated: true, now: Date.now() });
}


// Usage: Trigger revalidation when product is updated
// In admin endpoint
@router.post("/admin/products/{id}")
async def update_product(id: int, ...):
    await update_product_in_db(id, ...)
    
    # Trigger Next.js revalidation
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{settings.WEB_URL}/api/revalidate",
            json={"path": f"/products/{id}"},
            headers={"x-revalidate-secret": settings.REVALIDATE_SECRET},
        )
```

### Tag-Based Revalidation

```typescript
// GOOD: Tag-based revalidation
const getProducts = unstable_cache(
  async () => fetchProductsFromDB(),
  ['products-list'],
  { tags: ['products'] }
);

const getProduct = (id: string) => 
  unstable_cache(
    async () => fetchProductFromDB(id),
    ['product', id],
    { tags: [`product:${id}`, 'products'] }
  )();


// Revalidate all products when inventory changes
revalidateTag('products');

// Revalidate specific product
revalidateTag(`product:123`);
```

---

## Client-Side Rendering (CSR)

### When to Use CSR

✅ **Use CSR for:**
- Heavy interactive features (dashboards, editors)
- Real-time data (chat, live updates)
- After initial page load
- Authenticated app sections

### Implementation

```typescript
// GOOD: CSR for interactive features
// app/app/dashboard/page.tsx (Server Component)
'use client';

import { useQuery } from '@tanstack/react-query';

export default function DashboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => fetch('/api/dashboard').then(r => r.json()),
    refetchInterval: 30000,  // Refetch every 30s
  });
  
  if (isLoading) return <Skeleton />;
  
  return <DashboardView data={data} />;
}
```

### CSR with Loading State

```typescript
// GOOD: Loading skeleton for CSR
// app/app/analytics/page.tsx
'use client';

import { useQuery } from '@tanstack/react-query';

export default function AnalyticsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['analytics'],
    queryFn: () => fetch('/api/analytics').then(r => r.json()),
  });
  
  if (isLoading) {
    return (
      <div>
        <Skeleton className="h-32" />
        <Skeleton className="h-64 mt-4" />
      </div>
    );
  }
  
  if (error) {
    return <ErrorMessage error={error} />;
  }
  
  return <AnalyticsView data={data} />;
}
```

---

## Streaming and Suspense

### Server Component Streaming

```typescript
// GOOD: Stream slow data
// app/article/[id]/page.tsx

import { Suspense } from 'react';

export default function ArticlePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  return (
    <article>
      <h1>Article Title</h1>
      
      {/* Article content (fast) */}
      <ArticleContent id={params.id} />
      
      {/* Comments (slow) - streams in */}
      <Suspense fallback={<CommentsSkeleton />}>
        <Comments id={params.id} />
      </Suspense>
      
      {/* Related articles (slow) - streams in */}
      <Suspense fallback={<RelatedSkeleton />}>
        <RelatedArticles id={params.id} />
      </Suspense>
    </article>
  );
}


// Async component that streams
async function Comments({ id }: { id: string }) {
  // Slow query
  const comments = await getComments(id);
  return <CommentList comments={comments} />;
}
```

### Loading UI (loading.tsx)

```typescript
// app/dashboard/loading.tsx
export default function Loading() {
  return (
    <div>
      <Skeleton className="h-8 w-1/3" />
      <Skeleton className="h-32 mt-4" />
      <Skeleton className="h-64 mt-4" />
    </div>
  );
}
```

### Error UI (error.tsx)

```typescript
// app/dashboard/error.tsx
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
    console.error('Dashboard error:', error);
  }, [error]);
  
  return (
    <div>
      <h2>Something went wrong!</h2>
      <button onClick={() => reset()}>Try again</button>
    </div>
  );
}
```

---

## Edge Rendering

### Edge Functions (Vercel)

```typescript
// app/api/edge/route.ts
import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'edge';  // Run at edge

export async function GET(request: NextRequest) {
  // Geo-detection at the edge
  const country = request.geo?.country || 'US';
  const city = request.geo?.city || 'Unknown';
  
  return NextResponse.json({
    country,
    city,
    timestamp: new Date().toISOString(),
  });
}
```

### Edge Middleware (Authentication)

```typescript
// middleware.ts
import { NextRequest, NextResponse } from 'next/server';

export const config = {
  matcher: ['/dashboard/:path*', '/api/:path*'],
};

export async function middleware(request: NextRequest) {
  const token = request.cookies.get('session')?.value;
  
  if (!token) {
    return NextResponse.redirect(new URL('/login', request.url));
  }
  
  // Verify JWT at the edge (fast)
  const isValid = await verifyTokenAtEdge(token);
  
  if (!isValid) {
    return NextResponse.redirect(new URL('/login', request.url));
  }
  
  // Add user info to request headers
  const response = NextResponse.next();
  response.headers.set('x-user-id', extractUserId(token));
  
  return response;
}
```

### Edge-Compatible Code

```typescript
// GOOD: Edge-compatible (no Node.js APIs)
// Can run in V8 isolates
export const runtime = 'edge';

export async function GET() {
  // ✅ Can use: fetch, Request, Response, crypto, etc.
  const data = await fetch('https://api.example.com/data');
  return Response.json(await data.json());
}


// BAD: Not edge-compatible (uses Node.js APIs)
import { readFileSync } from 'fs';  // ❌ Not available in edge

export async function GET() {
  const data = readFileSync('/tmp/data.json');  // ❌ Fails at edge
  return Response.json(data);
}
```

---

## SEO Considerations

### Metadata API

```typescript
// GOOD: Static metadata
// app/about/page.tsx
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'About Us | MyWorld',
  description: 'Learn about MyWorld and our mission',
  keywords: ['myworld', 'about', 'company'],
  openGraph: {
    title: 'About Us',
    description: 'Learn about MyWorld',
    type: 'website',
    url: 'https://myworld.com/about',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'About Us',
    description: 'Learn about MyWorld',
  },
  alternates: {
    canonical: 'https://myworld.com/about',
  },
};

export default function AboutPage() {
  return <div>About content</div>;
}


// GOOD: Dynamic metadata
// app/blog/[slug]/page.tsx
export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const post = await getPost(slug);
  
  if (!post) return {};
  
  return {
    title: `${post.title} | MyWorld Blog`,
    description: post.excerpt,
    openGraph: {
      title: post.title,
      description: post.excerpt,
      images: [
        {
          url: post.coverImage,
          width: 1200,
          height: 630,
          alt: post.title,
        },
      ],
      type: 'article',
      publishedTime: post.publishedAt,
      authors: [post.author.name],
    },
  };
}
```

### Structured Data (JSON-LD)

```typescript
// GOOD: Add structured data for SEO
// app/blog/[slug]/page.tsx

export default async function BlogPostPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const post = await getPost(slug);
  
  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'BlogPosting',
    headline: post.title,
    description: post.excerpt,
    author: {
      '@type': 'Person',
      name: post.author.name,
    },
    datePublished: post.publishedAt,
    dateModified: post.updatedAt,
    image: post.coverImage,
  };
  
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <article>
        <h1>{post.title}</h1>
        <div>{post.content}</div>
      </article>
    </>
  );
}
```

### Sitemap

```typescript
// app/sitemap.ts
import type { MetadataRoute } from 'next';

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const posts = await getAllPosts();
  const products = await getAllProducts();
  
  return [
    {
      url: 'https://myworld.com',
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 1.0,
    },
    {
      url: 'https://myworld.com/about',
      lastModified: new Date(),
      changeFrequency: 'monthly',
      priority: 0.8,
    },
    ...posts.map(post => ({
      url: `https://myworld.com/blog/${post.slug}`,
      lastModified: post.updatedAt,
      changeFrequency: 'weekly',
      priority: 0.7,
    })),
    ...products.map(product => ({
      url: `https://myworld.com/products/${product.id}`,
      lastModified: product.updatedAt,
      changeFrequency: 'daily',
      priority: 0.9,
    })),
  ];
}
```

### Robots.txt

```typescript
// app/robots.ts
import type { MetadataRoute } from 'next';

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: '*',
        allow: '/',
        disallow: ['/api/', '/admin/', '/dashboard/'],
      },
    ],
    sitemap: 'https://myworld.com/sitemap.xml',
  };
}
```

---

## Best Practices Summary

| ✅ DO | ❌ DON'T |
|---|---|
| Use Server Components by default | Use Client Components unnecessarily |
| Use SSG for static content | SSR for marketing pages |
| Use ISR for semi-static content | Rebuild entire site for small changes |
| Use SSR for user-specific content | Cache user-specific data |
| Use CSR for interactive features | CSR for everything |
| Stream slow data with Suspense | Block page render on slow data |
| Use Edge functions for geo-routing | Run all logic in origin region |
| Add proper metadata for SEO | Forget about SEO |
| Generate sitemap.xml | Skip sitemap for SEO |
| Add structured data (JSON-LD) | Skip rich snippets |
| Pre-generate popular pages | Generate on-demand only |
| Cache static assets aggressively | Fetch assets on every request |
| Use Image component | Use raw `<img>` tags |
| Test rendering performance | Guess at performance |

---

## References

- [Next.js Rendering Documentation](https://nextjs.org/docs/app/building-your-application/rendering)
- [React Server Components](https://react.dev/reference/rsc/server-components)
- [Web Vitals](https://web.dev/vitals/)
- [ISR vs SSR vs SSG](https://vercel.com/blog/nextjs-server-side-rendering-vs-static-generation)
- [Edge Runtime](https://nextjs.org/docs/app/api-reference/edge)
- [Schema.org Structured Data](https://schema.org/)
- [Google Search Central - SEO](https://developers.google.com/search)
