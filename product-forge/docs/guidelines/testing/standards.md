# Testing Standards

> **Scope:** All Product Forge applications
> **Source:** Google Testing Blog + Martin Fowler + ISTQB + Test Pyramid
> **Version:** 1.0 | **Date:** 2026-08-24

---

## 1. Test Pyramid

```
        /\
       /  \      E2E Tests (Few)
      /----\     - Slow, expensive, brittle
     /      \    
    /--------\   Integration Tests (Some)
   /          \  - Test interactions
  /------------\ 
 /              \ Unit Tests (Many)
/________________\ - Fast, cheap, isolated
```

**Distribution:**
- **70% Unit Tests** — Fast, isolated, test business logic
- **20% Integration Tests** — Test component interactions
- **10% E2E Tests** — Test critical user journeys

---

## 2. Unit Tests

### 2.1 What to Test
- Pure functions
- Business logic
- Validation rules
- Edge cases
- Error handling

### 2.2 What NOT to Test
- Third-party libraries
- Framework code
- Trivial getters/setters

### 2.3 Python (pytest)
```python
import pytest
from decimal import Decimal
from services.pricing import calculate_total, InvalidTaxRateError

class TestCalculateTotal:
    """Test suite for calculate_total function."""
    
    def test_calculates_total_with_tax(self):
        items = [
            Item(price=Decimal("10.00"), quantity=2),
            Item(price=Decimal("5.00"), quantity=3),
        ]
        result = calculate_total(items, tax_rate=Decimal("0.08"))
        assert result == Decimal("37.80")  # 35.00 * 1.08
    
    def test_returns_zero_for_empty_items(self):
        result = calculate_total([], tax_rate=Decimal("0.08"))
        assert result == Decimal("0.00")
    
    def test_raises_error_for_negative_tax(self):
        with pytest.raises(InvalidTaxRateError, match="Tax rate cannot be negative"):
            calculate_total([], tax_rate=Decimal("-0.08"))
    
    @pytest.mark.parametrize("tax_rate,expected", [
        (Decimal("0.00"), Decimal("10.00")),
        (Decimal("0.05"), Decimal("10.50")),
        (Decimal("0.10"), Decimal("11.00")),
        (Decimal("0.20"), Decimal("12.00")),
    ])
    def test_various_tax_rates(self, tax_rate, expected):
        items = [Item(price=Decimal("10.00"), quantity=1)]
        result = calculate_total(items, tax_rate=tax_rate)
        assert result == expected
```

### 2.4 TypeScript (Vitest)
```typescript
import { describe, it, expect } from 'vitest';
import { calculateTotal, InvalidTaxRateError } from './pricing';

describe('calculateTotal', () => {
  it('calculates total with tax', () => {
    const items = [
      { price: 10.00, quantity: 2 },
      { price: 5.00, quantity: 3 },
    ];
    expect(calculateTotal(items, 0.08)).toBe(37.80);
  });
  
  it('returns zero for empty items', () => {
    expect(calculateTotal([], 0.08)).toBe(0);
  });
  
  it('throws for negative tax', () => {
    expect(() => calculateTotal([], -0.08)).toThrow(InvalidTaxRateError);
  });
  
  it.each([
    [0.00, 10.00],
    [0.05, 10.50],
    [0.10, 11.00],
    [0.20, 12.00],
  ])('handles tax rate %f', (taxRate, expected) => {
    const items = [{ price: 10.00, quantity: 1 }];
    expect(calculateTotal(items, taxRate)).toBe(expected);
  });
});
```

---

## 3. Integration Tests

### 3.1 What to Test
- API endpoints
- Database queries
- External service integrations
- Component interactions
- Authentication flows

### 3.2 API Tests (FastAPI)
```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_todo_success(client: AsyncClient, auth_headers: dict):
    # Arrange
    data = {"title": "Buy groceries", "description": "Milk, bread, eggs"}
    
    # Act
    response = await client.post("/api/v1/todos", json=data, headers=auth_headers)
    
    # Assert
    assert response.status_code == 201
    body = response.json()
    assert body["data"]["title"] == "Buy groceries"
    assert body["data"]["isCompleted"] is False
    assert "id" in body["data"]
    assert "createdAt" in body["data"]

@pytest.mark.asyncio
async def test_create_todo_validation_error(client: AsyncClient, auth_headers: dict):
    # Arrange
    data = {"title": ""}  # Empty title (invalid)
    
    # Act
    response = await client.post("/api/v1/todos", json=data, headers=auth_headers)
    
    # Assert
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert any(d["field"] == "title" for d in body["error"]["details"])

@pytest.mark.asyncio
async def test_create_todo_unauthorized(client: AsyncClient):
    # Act
    response = await client.post("/api/v1/todos", json={"title": "Test"})
    
    # Assert
    assert response.status_code == 401
```

### 3.3 Database Tests
```python
@pytest.mark.asyncio
async def test_user_repository_create(db: AsyncSession):
    # Arrange
    repo = UserRepository(db)
    data = UserCreate(email="test@example.com", name="Test User", password="password123")
    
    # Act
    user = await repo.create(data)
    
    # Assert
    assert user.id is not None
    assert user.email == "test@example.com"
    assert user.created_at is not None

@pytest.mark.asyncio
async def test_rls_isolation(db: AsyncSession):
    # Test that user A cannot see user B's todos
    user_a = await create_user(db, "a@example.com")
    user_b = await create_user(db, "b@example.com")
    todo_b = await create_todo(db, user_b.id, "B's todo")
    
    # Set session to user A
    await db.execute(text(f"SET app.current_user_id = '{user_a.id}'"))
    
    repo = TodoRepository(db)
    todos = await repo.list_for_user(user_a.id)
    
    # User A should not see user B's todo
    assert all(t.id != todo_b.id for t in todos)
```

---

## 4. E2E Tests (Playwright)

### 4.1 What to Test
- Critical user journeys
- Sign up / login flow
- Core feature flows
- Payment flows
- Cross-browser compatibility

### 4.2 Example
```typescript
import { test, expect } from '@playwright/test';

test.describe('Todo Management', () => {
  test.beforeEach(async ({ page }) => {
    // Login before each test
    await page.goto('/login');
    await page.getByLabel('Email').fill('test@example.com');
    await page.getByLabel('Password').fill('password123');
    await page.getByRole('button', { name: 'Sign In' }).click();
    await expect(page).toHaveURL('/dashboard');
  });
  
  test('user can create a todo', async ({ page }) => {
    await page.goto('/todos');
    await page.getByRole('button', { name: 'New Todo' }).click();
    await page.getByLabel('Title').fill('Buy groceries');
    await page.getByLabel('Description').fill('Milk, bread, eggs');
    await page.getByRole('button', { name: 'Save' }).click();
    
    await expect(page.getByText('Buy groceries')).toBeVisible();
    await expect(page.getByText('Milk, bread, eggs')).toBeVisible();
  });
  
  test('user can mark todo as complete', async ({ page }) => {
    await page.goto('/todos');
    const todo = page.getByTestId('todo-item').first();
    await todo.getByRole('checkbox').check();
    await expect(todo).toHaveClass(/completed/);
  });
  
  test('shows validation error for empty title', async ({ page }) => {
    await page.goto('/todos');
    await page.getByRole('button', { name: 'New Todo' }).click();
    await page.getByRole('button', { name: 'Save' }).click();
    
    await expect(page.getByText('Title is required')).toBeVisible();
  });
});
```

### 4.3 Page Object Model
```typescript
// pages/LoginPage.ts
import { type Page, expect } from '@playwright/test';

export class LoginPage {
  constructor(private page: Page) {}
  
  async goto() {
    await this.page.goto('/login');
  }
  
  async login(email: string, password: string) {
    await this.page.getByLabel('Email').fill(email);
    await this.page.getByLabel('Password').fill(password);
    await this.page.getByRole('button', { name: 'Sign In' }).click();
  }
  
  async expectError(message: string) {
    await expect(this.page.getByRole('alert')).toContainText(message);
  }
}

// Usage in test
test('invalid login', async ({ page }) => {
  const loginPage = new LoginPage(page);
  await loginPage.goto();
  await loginPage.login('wrong@example.com', 'wrong');
  await loginPage.expectError('Invalid credentials');
});
```

---

## 5. Test Organization

### 5.1 Co-located Tests
```
src/
├── services/
│   ├── pricing.ts
│   └── pricing.test.ts          # Co-located unit test
├── components/
│   ├── Button.tsx
│   └── Button.test.tsx          # Co-located component test
└── pages/
    ├── LoginPage.tsx
    └── LoginPage.test.tsx
```

### 5.2 Separate Test Directory (Alternative)
```
tests/
├── unit/
│   └── services/
│       └── pricing.test.ts
├── integration/
│   └── api/
│       └── todos.test.ts
└── e2e/
    └── flows/
        └── todo-management.spec.ts
```

### 5.3 Naming Convention
- **File:** `<unit>.test.ts` or `<unit>.spec.ts`
- **Test:** `describe('ComponentName', () => { it('does X', ...) })`
- **Test:** `def test_<scenario>_<expected>(): ...`

---

## 6. Test Quality

### 6.1 AAA Pattern (Arrange-Act-Assert)
```python
def test_calculate_total():
    # Arrange
    items = [Item(price=10, quantity=2)]
    tax_rate = 0.08
    
    # Act
    result = calculate_total(items, tax_rate)
    
    # Assert
    assert result == 21.60
```

### 6.2 One Assertion Concept Per Test
```python
# Bad: Multiple unrelated assertions
def test_user():
    user = create_user()
    assert user.email == "test@example.com"
    assert user.is_active is True
    assert user.created_at is not None
    assert len(user.todos) == 0

# Good: Separate tests
def test_user_has_correct_email():
    user = create_user()
    assert user.email == "test@example.com"

def test_user_is_active_by_default():
    user = create_user()
    assert user.is_active is True

def test_new_user_has_no_todos():
    user = create_user()
    assert len(user.todos) == 0
```

### 6.3 Use Descriptive Names
```python
# Bad
def test_todo():
    pass

# Good
def test_user_can_create_todo_with_valid_data():
    pass

def test_create_todo_with_empty_title_raises_validation_error():
    pass

def test_user_cannot_access_other_users_todos():
    pass
```

### 6.4 Don't Test Implementation Details
```python
# Bad: Tests implementation
def test_uses_specific_database_query():
    with mock.patch('app.db.execute') as mock_execute:
        create_todo(data)
        mock_execute.assert_called_once_with("INSERT INTO todos ...")

# Good: Tests behavior
def test_creates_todo_in_database():
    todo = create_todo(data)
    assert todo.id is not None
    retrieved = get_todo(todo.id)
    assert retrieved is not None
```

---

## 7. Test Data

### 7.1 Use Factories
```python
# factories.py
import factory
from factory import fuzzy

class UserFactory(factory.Factory):
    class Meta:
        model = User
    
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    name = factory.Faker('name')
    is_active = True
    created_at = factory.LazyFunction(datetime.utcnow)

# Usage
user = UserFactory()
admin = UserFactory(is_admin=True)
```

### 7.2 Use Fixtures
```python
# conftest.py
@pytest.fixture
async def db():
    """Create test database connection."""
    async with AsyncSession(test_engine) as session:
        yield session
        await session.rollback()

@pytest.fixture
async def client(db):
    """Create test client with database."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture
async def auth_headers(user):
    """Create auth headers for test user."""
    token = create_access_token(user.id)
    return {"Authorization": f"Bearer {token}"}
```

### 7.3 Don't Share State Between Tests
```python
# Bad: Shared state
user_id = None

def test_create_user():
    global user_id
    user = create_user()
    user_id = user.id  # Set shared state

def test_get_user():
    response = get_user(user_id)  # Depends on previous test!
    assert response.email == "test@example.com"

# Good: Independent tests
def test_create_user():
    user = create_user()
    assert user.id is not None

def test_get_user(db, user_factory):
    user = user_factory()
    response = get_user(user.id)
    assert response.email == user.email
```

---

## 8. Mocking

### 8.1 When to Mock
- External services (APIs, databases in unit tests)
- Time/dates
- Random values
- File system

### 8.2 When NOT to Mock
- The system under test
- Pure functions
- Simple data structures

### 8.3 Python Mocking
```python
from unittest.mock import patch, MagicMock

def test_sends_email_on_signup():
    with patch('services.email.send') as mock_send:
        signup_user("test@example.com")
        mock_send.assert_called_once_with(
            to="test@example.com",
            template="welcome",
        )

def test_external_api_timeout(monkeypatch):
    # Mock external API to timeout
    mock_api = MagicMock(side_effect=TimeoutError())
    monkeypatch.setattr('services.weather_api.get', mock_api)
    
    result = get_weather("London")
    assert result is None  # Should handle timeout gracefully
```

### 8.4 TypeScript Mocking
```typescript
import { vi } from 'vitest';

vi.mock('./api', () => ({
  fetchUser: vi.fn().mockResolvedValue({ id: 1, name: 'Test' }),
}));

test('displays user name', async () => {
  render(<UserProfile userId={1} />);
  expect(await screen.findByText('Test')).toBeInTheDocument();
});
```

---

## 9. Coverage

### 9.1 Targets
- **Unit tests:** 80%+ coverage
- **Integration tests:** 60%+ coverage
- **E2E tests:** All critical user journeys

### 9.2 What to Cover
- All public functions/methods
- All branches (if/else)
- All error paths
- Edge cases (empty, null, boundary)

### 9.3 What NOT to Aim For 100%
- Trivial code
- Framework boilerplate
- Generated code
- Configuration files

### 9.4 Configuration
```toml
# pyproject.toml
[tool.coverage.run]
source = ["src", "app"]
omit = ["*/tests/*", "*/migrations/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if __name__ == .__main__.:",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
]
```

---

## 10. Continuous Integration

### 10.1 Run Tests on Every PR
```yaml
# .github/workflows/test.yml
name: Tests
on: [pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - run: pip install -e ".[dev]"
      - run: pytest --cov=src --cov-report=xml
      - run: ruff check .
      - run: mypy src
```

### 10.2 Test Gates
- All tests must pass
- Coverage must not decrease
- No new linting errors
- Type checking must pass

---

## 11. Performance Testing

### 11.1 Load Testing (k6, Locust)
```javascript
// k6 load test
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 100 },  // Ramp up to 100 users
    { duration: '1m', target: 100 },   // Stay at 100 users
    { duration: '30s', target: 0 },    // Ramp down
  ],
};

export default function () {
  const res = http.get('https://api.example.com/api/v1/todos');
  check(res, {
    'status is 200': (r) => r.status === 200,
    'response time < 500ms': (r) => r.timings.duration < 500,
  });
  sleep(1);
}
```

### 11.2 Benchmark Critical Paths
```python
@pytest.mark.benchmark
def test_user_creation_performance(benchmark):
    result = benchmark(create_user, email="test@example.com")
    assert result is not None
```

---

## 12. Security Testing

### 12.1 Dependency Scanning
```bash
# Python
pip-audit
safety check

# JavaScript
npm audit
snyk test
```

### 12.2 SAST (Static Analysis)
```bash
# Python
bandit -r src/

# JavaScript
eslint --plugin security src/
```

### 12.3 DAST (Dynamic Analysis)
- OWASP ZAP
- Burp Suite
- Run against staging environment

---

## 13. Accessibility Testing

### 13.1 Automated (axe-core)
```typescript
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('homepage is accessible', async ({ page }) => {
  await page.goto('/');
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});
```

### 13.2 Manual Testing
- Keyboard navigation (no mouse)
- Screen reader (NVDA, JAWS, VoiceOver)
- Color contrast checker
- Zoom to 200%

---

## 14. Anti-Patterns to Avoid

| Anti-Pattern | Why | Instead |
|---|---|---|
| Testing implementation | Brittle, breaks on refactor | Test behavior |
| Shared state between tests | Order-dependent, flaky | Independent tests |
| Mocking everything | Tests nothing real | Mock only boundaries |
| No assertions | Test passes always | Clear assertions |
| One giant test | Hard to debug | Small focused tests |
| Slow tests | Discourages running | Fast unit tests, fewer E2E |
| Testing private methods | Couples to implementation | Test public API |
| Flaky tests | Ignored by team | Fix or remove |
| 100% coverage goal | Diminishing returns | 80% meaningful coverage |
| No CI integration | Breaks ignored | Tests in CI pipeline |
| Testing framework code | Wasted effort | Trust the framework |

---

## 15. References

- [Google Testing Blog](https://testing.googleblog.com/)
- [Martin Fowler - Testing](https://martinfowler.com/testing/)
- [Test Pyramid](https://martinfowler.com/articles/practical-test-pyramid.html)
- [Playwright Documentation](https://playwright.dev/)
- [pytest Documentation](https://docs.pytest.org/)
- [Vitest Documentation](https://vitest.dev/)
- [OWASP Testing Guide](https://owasp.org/www-project-web-security-testing-guide/)

---

## 16. Enforcement

- **CI/CD pipeline** runs all tests on every PR
- **Coverage gate** in CI (minimum 80% for new code)
- **Code review** includes test review
- **Pre-commit hooks** for linting
- **Test naming** conventions enforced
