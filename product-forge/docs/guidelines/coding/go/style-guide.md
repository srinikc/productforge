# Go Engineering Standards

> Idiomatic Go for backend services, CLI tools, and infrastructure code in MyWorld Central Portal.

## Table of Contents

1. [Project Structure](#project-structure)
2. [Code Style and Formatting](#code-style-and-formatting)
3. [Naming Conventions](#naming-conventions)
4. [Error Handling](#error-handling)
5. [Concurrency](#concurrency)
6. [Interfaces and Dependencies](#interfaces-and-dependencies)
7. [Testing](#testing)
8. [HTTP Services](#http-services)
9. [Database Access](#database-access)
10. [Configuration](#configuration)
11. [Logging](#logging)
12. [Performance](#performance)

---

## Project Structure

### Standard Layout

```
myapp/
├── cmd/
│   └── myapp/
│       └── main.go           # Entry point
├── internal/                  # Private application code
│   ├── api/                   # HTTP handlers
│   ├── service/               # Business logic
│   ├── repository/            # Data access
│   ├── model/                 # Domain models
│   ├── config/                # Configuration
│   └── middleware/            # HTTP middleware
├── pkg/                       # Public library code (use sparingly)
│   └── mylib/
├── api/                       # API definitions (OpenAPI, protobuf)
├── web/                       # Static assets
├── configs/                   # Config files
├── deployments/               # Docker, k8s manifests
├── docs/                      # Documentation
├── test/                      # Integration tests
├── go.mod
├── go.sum
├── Makefile
└── README.md
```

### go.mod

```go
module github.com/myworld/myapp

go 1.22

require (
    github.com/gin-gonic/gin v1.10.0
    github.com/jackc/pgx/v5 v5.5.5
    github.com/spf13/viper v1.18.2
    go.uber.org/zap v1.27.0
    github.com/stretchr/testify v1.9.0
)

require (
    // indirect dependencies...
)
```

---

## Code Style and Formatting

### gofmt and golangci-lint

```bash
# Format code (run before every commit)
gofmt -s -w .
goimports -w .

# Run linters
golangci-lint run

# Vet
go vet ./...
```

### Code Organization in Files

```go
// GOOD: Organized file structure
package user

// 1. Imports (stdlib, then third-party, then internal)
import (
    "context"
    "fmt"
    "time"

    "github.com/gin-gonic/gin"
    "github.com/jackc/pgx/v5"

    "github.com/myworld/myapp/internal/model"
    "github.com/myworld/myapp/internal/repository"
)

// 2. Constants
const (
    DefaultPageSize = 20
    MaxPageSize     = 100
)

// 3. Variables (avoid package-level mutable state)
var (
    ErrUserNotFound = errors.New("user not found")
    ErrUserExists   = errors.New("user already exists")
)

// 4. Types
type Service struct {
    repo   repository.UserRepository
    logger *zap.Logger
}

// 5. Constructor
func NewService(repo repository.UserRepository, logger *zap.Logger) *Service {
    return &Service{
        repo:   repo,
        logger: logger,
    }
}

// 6. Methods
func (s *Service) GetUser(ctx context.Context, id int64) (*model.User, error) {
    // ...
}

// 7. Helper functions
func validateEmail(email string) error {
    // ...
}
```

### Function Signatures

```go
// GOOD: Context first, then inputs, then options
func (s *Service) CreateUser(
    ctx context.Context,
    input CreateUserInput,
    opts ...CreateUserOption,
) (*model.User, error) {
    // ...
}


// GOOD: Use struct for many parameters
type CreateUserInput struct {
    Email     string
    FullName  string
    Password  string
}

func (s *Service) CreateUser(ctx context.Context, input CreateUserInput) (*model.User, error) {
    // ...
}


// BAD: Too many parameters, not using struct
func (s *Service) CreateUser(
    ctx context.Context,
    email, fullName, password, phone, address, city, country string,
) (*model.User, error) {
    // ❌ Hard to read, easy to mix up
}
```

### Comments

```go
// GOOD: Doc comments for exported identifiers
// Package user provides user management functionality.
package user

// Service handles user-related business logic.
type Service struct {
    // ...
}

// GetUser retrieves a user by ID.
// Returns ErrUserNotFound if the user doesn't exist.
func (s *Service) GetUser(ctx context.Context, id int64) (*model.User, error) {
    // ...
}


// GOOD: Inline comments explain WHY, not WHAT
// Use bcrypt cost of 12 to balance security and performance.
// Higher values are more secure but slower.
const bcryptCost = 12


// BAD: Comments that just repeat the code
// Increment i
i++  // ❌ Obvious from code


// BAD: Unnecessary comments
// This is the user service
// It handles users
type Service struct {  // ❌ Says nothing
    // ...
}
```

---

## Naming Conventions

### General Rules

```go
// GOOD: Idiomatic Go naming
package user              // lowercase, single word
type Service struct{}      // PascalCase for exported
type repository struct{}   // camelCase for unexported
func GetUser() {}          // PascalCase for exported functions
func validateEmail() {}    // camelCase for unexported
const MaxRetries = 3       // PascalCase for exported constants
const defaultTimeout = 30  // camelCase for unexported
var ErrNotFound = errors.New("not found")  // Err prefix for errors
```

### Interface Naming

```go
// GOOD: Single-method interfaces end in "-er"
type Reader interface {
    Read(p []byte) (n int, err error)
}

type Writer interface {
    Write(p []byte) (n int, err error)
}

type UserRepository interface {  // Multi-method interface
    Get(ctx context.Context, id int64) (*model.User, error)
    Create(ctx context.Context, user *model.User) error
    Update(ctx context.Context, user *model.User) error
    Delete(ctx context.Context, id int64) error
}


// BAD: Generic interface names
type IUserService interface{}  // ❌ No "I" prefix in Go
type UserServiceInterface interface{}  // ❌ Redundant
type AbstractUser interface{}  // ❌ Not idiomatic
```

### Variable Naming

```go
// GOOD: Short, meaningful names
for i, v := range items {  // i = index, v = value
}

// GOOD: Longer names for larger scopes
userRepository := repo.NewUserRepository(db)

// BAD: Cryptic abbreviations
for ix, val := range items {  // ❌ Use i, v
}
usrRepo := repo.NewUserRepository(db)  // ❌ Use userRepository
```

### Acronyms

```go
// GOOD: Acronyms all same case
type HTTPClient struct{}     // Not HttpClient
type URLParser struct{}      // Not UrlParser
type userID int64            // Not userId
func GetAPIKey() string {}   // Not GetApiKey


// GOOD: All caps for acronyms
apiURL := "https://api.example.com"
userID := 12345
httpResponse, err := http.Get(url)
```

---

## Error Handling

### Error Creation and Wrapping

```go
// GOOD: Use errors.New or fmt.Errorf for errors
var (
    ErrUserNotFound = errors.New("user not found")
    ErrInvalidEmail = errors.New("invalid email")
)

func (s *Service) GetUser(ctx context.Context, id int64) (*model.User, error) {
    user, err := s.repo.Get(ctx, id)
    if err != nil {
        if errors.Is(err, repository.ErrNotFound) {
            return nil, fmt.Errorf("get user %d: %w", ErrUserNotFound, err)
        }
        return nil, fmt.Errorf("get user %d: %w", id, err)
    }
    return user, nil
}


// GOOD: Custom error types with context
type ValidationError struct {
    Field   string
    Message string
}

func (e *ValidationError) Error() string {
    return fmt.Sprintf("validation failed for %s: %s", e.Field, e.Message)
}


// GOOD: Sentinel errors for comparison
var (
    ErrNotFound     = errors.New("not found")
    ErrUnauthorized = errors.New("unauthorized")
    ErrForbidden    = errors.New("forbidden")
)
```

### Error Handling Patterns

```go
// GOOD: Check errors immediately
result, err := doSomething()
if err != nil {
    return fmt.Errorf("do something: %w", err)
}

// GOOD: Use errors.Is for sentinel errors
if errors.Is(err, ErrNotFound) {
    return nil, http.StatusNotFound
}

// GOOD: Use errors.As for error types
var validationErr *ValidationError
if errors.As(err, &validationErr) {
    return http.StatusBadRequest, validationErr.Message
}


// BAD: Ignoring errors
result, _ := doSomething()  // ❌ Error ignored

// BAD: Storing error in variable but not checking
result, err := doSomething()
return result  // ❌ Forgot to check err
```

### Panic vs Error

```go
// GOOD: Return errors for expected failures
func (s *Service) GetUser(ctx context.Context, id int64) (*model.User, error) {
    user, err := s.repo.Get(ctx, id)
    if err != nil {
        return nil, err
    }
    return user, nil
}


// GOOD: Panic only for truly exceptional, unrecoverable situations
func init() {
    if config == nil {
        panic("config must be initialized")  // ✅ Init-time error
    }
}


// BAD: Panic for normal control flow
func GetUser(id int64) *model.User {
    user, err := repo.Get(id)
    if err != nil {
        panic(err)  // ❌ Don't panic for expected errors
    }
    return user
}
```

---

## Concurrency

### Goroutines

```go
// GOOD: Use goroutines for concurrent work
func (s *Service) GetDashboardData(ctx context.Context, userID int64) (*Dashboard, error) {
    var (
        wg      sync.WaitGroup
        user    *model.User
        posts   []model.Post
        stats   *Stats
        userErr error
        postErr error
        statErr error
    )
    
    wg.Add(3)
    
    go func() {
        defer wg.Done()
        user, userErr = s.userService.GetUser(ctx, userID)
    }()
    
    go func() {
        defer wg.Done()
        posts, postErr = s.postService.GetUserPosts(ctx, userID)
    }()
    
    go func() {
        defer wg.Done()
        stats, statErr = s.statsService.GetUserStats(ctx, userID)
    }()
    
    wg.Wait()
    
    if userErr != nil {
        return nil, fmt.Errorf("get user: %w", userErr)
    }
    
    return &Dashboard{
        User:  user,
        Posts: posts,
        Stats: stats,
    }, nil
}
```

### Channels

```go
// GOOD: Use channels for signaling
func (s *Service) ProcessJobs(ctx context.Context, jobs <-chan Job) {
    for {
        select {
        case <-ctx.Done():
            return
        case job, ok := <-jobs:
            if !ok {
                return  // Channel closed
            }
            if err := s.processJob(ctx, job); err != nil {
                s.logger.Error("process job", zap.Error(err))
            }
        }
    }
}


// GOOD: Buffered channels for bounded concurrency
func (s *Service) ProcessBatch(ctx context.Context, items []Item) error {
    const maxConcurrency = 10
    sem := make(chan struct{}, maxConcurrency)
    errCh := make(chan error, len(items))
    
    for _, item := range items {
        sem <- struct{}{}
        go func(item Item) {
            defer func() { <-sem }()
            if err := s.processItem(ctx, item); err != nil {
                errCh <- err
            }
        }(item)
    }
    
    // Wait for all to complete
    for i := 0; i < cap(sem); i++ {
        sem <- struct{}{}
    }
    close(errCh)
    
    // Collect errors
    var errs []error
    for err := range errCh {
        errs = append(errs, err)
    }
    
    if len(errs) > 0 {
        return errors.Join(errs...)
    }
    return nil
}
```

### errgroup (Synchronized Concurrent Operations)

```go
import "golang.org/x/sync/errgroup"

// GOOD: Use errgroup for concurrent error handling
func (s *Service) FetchUserData(ctx context.Context, userID int64) (*UserData, error) {
    g, ctx := errgroup.WithContext(ctx)
    
    var (
        user  *model.User
        posts []model.Post
        stats *Stats
    )
    
    g.Go(func() error {
        var err error
        user, err = s.userService.GetUser(ctx, userID)
        return err
    })
    
    g.Go(func() error {
        var err error
        posts, err = s.postService.GetUserPosts(ctx, userID)
        return err
    })
    
    g.Go(func() error {
        var err error
        stats, err = s.statsService.GetUserStats(ctx, userID)
        return err
    })
    
    if err := g.Wait(); err != nil {
        return nil, fmt.Errorf("fetch user data: %w", err)
    }
    
    return &UserData{User: user, Posts: posts, Stats: stats}, nil
}
```

### Context

```go
// GOOD: Always pass context as first parameter
func (s *Service) GetUser(ctx context.Context, id int64) (*model.User, error) {
    // Context handles cancellation and timeouts
    user, err := s.repo.Get(ctx, id)
    if err != nil {
        return nil, err
    }
    return user, nil
}


// GOOD: Use context for cancellation
ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
defer cancel()

user, err := s.GetUser(ctx, 123)
if err != nil {
    if errors.Is(err, context.DeadlineExceeded) {
        // Handle timeout
    }
    return err
}
```

### Mutexes

```go
// GOOD: Protect shared state with mutex
type Counter struct {
    mu    sync.Mutex
    count int
}

func (c *Counter) Increment() {
    c.mu.Lock()
    defer c.mu.Unlock()
    c.count++
}

func (c *Counter) Value() int {
    c.mu.Lock()
    defer c.mu.Unlock()
    return c.count
}


// GOOD: Use sync.RWMutex for read-heavy workloads
type Cache struct {
    mu    sync.RWMutex
    items map[string]interface{}
}

func (c *Cache) Get(key string) (interface{}, bool) {
    c.mu.RLock()
    defer c.mu.RUnlock()
    val, ok := c.items[key]
    return val, ok
}

func (c *Cache) Set(key string, value interface{}) {
    c.mu.Lock()
    defer c.mu.Unlock()
    c.items[key] = value
}
```

---

## Interfaces and Dependencies

### Accept Interfaces, Return Structs

```go
// GOOD: Function accepts interface
type UserRepository interface {
    Get(ctx context.Context, id int64) (*model.User, error)
    Create(ctx context.Context, user *model.User) error
}

func NewService(repo UserRepository) *Service {
    return &Service{repo: repo}
}

// GOOD: Constructor returns concrete type
func NewUserRepository(db *pgxpool.Pool) *UserRepositoryImpl {
    return &UserRepositoryImpl{db: db}
}


// BAD: Function returns interface
func NewService() ServiceInterface {  // ❌
    return &serviceImpl{}
}
```

### Small Interfaces

```go
// GOOD: Small, focused interface
type UserGetter interface {
    GetUser(ctx context.Context, id int64) (*model.User, error)
}

type UserCreator interface {
    CreateUser(ctx context.Context, user *model.User) error
}


// GOOD: Compose interfaces
type UserRepository interface {
    UserGetter
    UserCreator
    UserUpdater
    UserDeleter
}


// BAD: Large interface with many unrelated methods
type Repository interface {
    GetUser() error
    CreateUser() error
    UpdateUser() error
    DeleteUser() error
    GetPost() error
    CreatePost() error
    UpdatePost() error
    DeletePost() error
    // ... 50 more methods
}
```

### Dependency Injection

```go
// GOOD: Constructor injection
type Service struct {
    userRepo  UserRepository
    postRepo  PostRepository
    logger    *zap.Logger
    cache     Cache
}

func NewService(
    userRepo UserRepository,
    postRepo PostRepository,
    logger *zap.Logger,
    cache Cache,
) *Service {
    return &Service{
        userRepo: userRepo,
        postRepo: postRepo,
        logger:   logger,
        cache:    cache,
    }
}


// GOOD: Wire dependencies in main.go
func main() {
    db := initDB()
    cache := initCache()
    logger := initLogger()
    
    userRepo := repository.NewUserRepository(db)
    postRepo := repository.NewPostRepository(db)
    
    userService := service.NewUserService(userRepo, logger)
    postService := service.NewPostService(postRepo, logger)
    
    handler := api.NewHandler(userService, postService, logger)
    
    router := setupRouter(handler, logger)
    router.Run(":8080")
}
```

---

## Testing

### Table-Driven Tests

```go
// GOOD: Table-driven tests
func TestValidateEmail(t *testing.T) {
    tests := []struct {
        name    string
        email   string
        wantErr bool
    }{
        {"valid email", "user@example.com", false},
        {"valid with subdomain", "user@mail.example.com", false},
        {"missing @", "userexample.com", true},
        {"missing domain", "user@", true},
        {"empty", "", true},
    }
    
    for _, tt := range tests {
        tt := tt  // Capture range variable
        t.Run(tt.name, func(t *testing.T) {
            err := validateEmail(tt.email)
            if (err != nil) != tt.wantErr {
                t.Errorf("validateEmail(%q) error = %v, wantErr %v", tt.email, err, tt.wantErr)
            }
        })
    }
}
```

### Test Helpers

```go
// GOOD: Use t.Helper() for cleaner test output
func assertNoError(t *testing.T, err error) {
    t.Helper()
    if err != nil {
        t.Fatalf("unexpected error: %v", err)
    }
}

func assertEqual(t *testing.T, got, want interface{}) {
    t.Helper()
    if !reflect.DeepEqual(got, want) {
        t.Errorf("got %v, want %v", got, want)
    }
}
```

### Mocking

```go
// GOOD: Use interfaces for mocking
type UserRepository interface {
    Get(ctx context.Context, id int64) (*model.User, error)
    Create(ctx context.Context, user *model.User) error
}

// GOOD: Mock implementation
type mockUserRepository struct {
    getFunc    func(ctx context.Context, id int64) (*model.User, error)
    createFunc func(ctx context.Context, user *model.User) error
}

func (m *mockUserRepository) Get(ctx context.Context, id int64) (*model.User, error) {
    return m.getFunc(ctx, id)
}

func (m *mockUserRepository) Create(ctx context.Context, user *model.User) error {
    return m.createFunc(ctx, user)
}

func newMockUserRepository() *mockUserRepository {
    return &mockUserRepository{
        getFunc: func(ctx context.Context, id int64) (*model.User, error) {
            return &model.User{ID: id, Email: "test@example.com"}, nil
        },
    }
}


// GOOD: Test with mock
func TestService_GetUser(t *testing.T) {
    repo := newMockUserRepository()
    service := NewService(repo, zap.NewNop())
    
    user, err := service.GetUser(context.Background(), 1)
    
    assertNoError(t, err)
    assertEqual(t, user.ID, int64(1))
    assertEqual(t, user.Email, "test@example.com")
}
```

### Integration Tests

```go
// GOOD: Integration test with real database
//go:build integration
// +build integration

func TestUserRepository_Integration(t *testing.T) {
    // Skip in unit tests
    if testing.Short() {
        t.Skip("Skipping integration test")
    }
    
    db := setupTestDB(t)
    defer db.Close()
    
    repo := repository.NewUserRepository(db)
    
    t.Run("Create and Get", func(t *testing.T) {
        user := &model.User{
            Email: "test@example.com",
            FullName: "Test User",
        }
        
        err := repo.Create(context.Background(), user)
        assertNoError(t, err)
        
        got, err := repo.Get(context.Background(), user.ID)
        assertNoError(t, err)
        assertEqual(t, got.Email, user.Email)
    })
}
```

---

## HTTP Services

### HTTP Handlers (Gin)

```go
// GOOD: Handler structure
type Handler struct {
    userService UserService
    logger      *zap.Logger
}

func NewHandler(userService UserService, logger *zap.Logger) *Handler {
    return &Handler{
        userService: userService,
        logger:      logger,
    }
}

// GET /users/:id
func (h *Handler) GetUser(c *gin.Context) {
    id, err := strconv.ParseInt(c.Param("id"), 10, 64)
    if err != nil {
        c.JSON(http.StatusBadRequest, gin.H{"error": "invalid id"})
        return
    }
    
    user, err := h.userService.GetUser(c.Request.Context(), id)
    if err != nil {
        if errors.Is(err, ErrUserNotFound) {
            c.JSON(http.StatusNotFound, gin.H{"error": "user not found"})
            return
        }
        h.logger.Error("get user", zap.Error(err))
        c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
        return
    }
    
    c.JSON(http.StatusOK, user)
}
```

### Middleware

```go
// GOOD: Logging middleware
func LoggingMiddleware(logger *zap.Logger) gin.HandlerFunc {
    return func(c *gin.Context) {
        start := time.Now()
        path := c.Request.URL.Path
        
        c.Next()
        
        duration := time.Since(start)
        status := c.Writer.Status()
        
        logger.Info("http request",
            zap.String("method", c.Request.Method),
            zap.String("path", path),
            zap.Int("status", status),
            zap.Duration("duration", duration),
        )
    }
}


// GOOD: Recovery middleware (catches panics)
func RecoveryMiddleware(logger *zap.Logger) gin.HandlerFunc {
    return func(c *gin.Context) {
        defer func() {
            if err := recover(); err != nil {
                logger.Error("panic recovered",
                    zap.Any("error", err),
                    zap.String("path", c.Request.URL.Path),
                )
                c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
                c.Abort()
            }
        }()
        c.Next()
    }
}
```

### Router Setup

```go
func SetupRouter(h *Handler, logger *zap.Logger) *gin.Engine {
    r := gin.New()
    
    // Middleware
    r.Use(LoggingMiddleware(logger))
    r.Use(RecoveryMiddleware(logger))
    
    // Health check
    r.GET("/health", func(c *gin.Context) {
        c.JSON(http.StatusOK, gin.H{"status": "ok"})
    })
    
    // API routes
    v1 := r.Group("/api/v1")
    {
        users := v1.Group("/users")
        {
            users.GET("/:id", h.GetUser)
            users.POST("/", h.CreateUser)
            users.PUT("/:id", h.UpdateUser)
            users.DELETE("/:id", h.DeleteUser)
        }
    }
    
    return r
}
```

---

## Database Access

### SQL Queries (pgx)

```go
// GOOD: Use parameterized queries (prevent SQL injection)
func (r *UserRepositoryImpl) Get(ctx context.Context, id int64) (*model.User, error) {
    var user model.User
    
    err := r.db.QueryRow(ctx,
        "SELECT id, email, full_name, created_at FROM users WHERE id = $1",
        id,
    ).Scan(&user.ID, &user.Email, &user.FullName, &user.CreatedAt)
    
    if err != nil {
        if errors.Is(err, pgx.ErrNoRows) {
            return nil, ErrNotFound
        }
        return nil, fmt.Errorf("query user: %w", err)
    }
    
    return &user, nil
}


// BAD: String concatenation (SQL injection risk)
query := "SELECT * FROM users WHERE id = " + userInput  // ❌ NEVER
```

### Transactions

```go
// GOOD: Use transactions for related operations
func (s *Service) CreateUserWithProfile(
    ctx context.Context,
    user *model.User,
    profile *model.Profile,
) error {
    tx, err := s.db.Begin(ctx)
    if err != nil {
        return fmt.Errorf("begin tx: %w", err)
    }
    defer tx.Rollback(ctx)  // Safe to call even after commit
    
    // Create user
    if err := s.userRepo.CreateTx(ctx, tx, user); err != nil {
        return fmt.Errorf("create user: %w", err)
    }
    
    // Create profile
    profile.UserID = user.ID
    if err := s.profileRepo.CreateTx(ctx, tx, profile); err != nil {
        return fmt.Errorf("create profile: %w", err)
    }
    
    // Commit
    if err := tx.Commit(ctx); err != nil {
        return fmt.Errorf("commit tx: %w", err)
    }
    
    return nil
}
```

---

## Configuration

### Viper Configuration

```go
type Config struct {
    App      AppConfig
    Database DatabaseConfig
    Redis    RedisConfig
    JWT      JWTConfig
}

type AppConfig struct {
    Env      string
    Port     int
    LogLevel string
}

type DatabaseConfig struct {
    URL          string
    MaxConns     int
    MinConns     int
    MaxConnLife  time.Duration
}

func LoadConfig() (*Config, error) {
    viper.SetConfigName("config")
    viper.AddConfigPath("./configs")
    viper.AutomaticEnv()
    
    if err := viper.ReadInConfig(); err != nil {
        return nil, fmt.Errorf("read config: %w", err)
    }
    
    var cfg Config
    if err := viper.Unmarshal(&cfg); err != nil {
        return nil, fmt.Errorf("unmarshal config: %w", err)
    }
    
    return &cfg, nil
}
```

### Environment Variables

```go
// GOOD: 12-factor config from environment
func getEnv(key, defaultValue string) string {
    if value := os.Getenv(key); value != "" {
        return value
    }
    return defaultValue
}

func getEnvInt(key string, defaultValue int) int {
    if value := os.Getenv(key); value != "" {
        if intValue, err := strconv.Atoi(value); err == nil {
            return intValue
        }
    }
    return defaultValue
}
```

---

## Logging

### Structured Logging (Zap)

```go
// GOOD: Structured logging
logger.Info("user created",
    zap.Int64("user_id", user.ID),
    zap.String("email", user.Email),
    zap.String("source", "registration"),
)


// GOOD: Logger with context
func WithRequestID(ctx context.Context, logger *zap.Logger) *zap.Logger {
    requestID := ctx.Value("request_id")
    if requestID != nil {
        return logger.With(zap.String("request_id", requestID.(string)))
    }
    return logger
}


// GOOD: Different log levels
logger.Debug("detailed info", zap.Any("data", data))    // Verbose
logger.Info("normal event", zap.String("action", "create"))  // Normal
logger.Warn("potential issue", zap.Int("retries", 3))  // Warning
logger.Error("operation failed", zap.Error(err))  // Error
logger.Fatal("unrecoverable", zap.Error(err))  // Exit 1
```

### Avoid Logging in Hot Paths

```go
// BAD: Logging in tight loop (expensive)
for _, item := range items {
    logger.Debug("processing item", zap.Any("item", item))  // ❌
    processItem(item)
}

// GOOD: Log summary
logger.Info("processing batch", zap.Int("count", len(items)))
for _, item := range items {
    processItem(item)
}
logger.Info("batch processed", zap.Int("count", len(items)))
```

---

## Performance

### Profiling

```go
// GOOD: Use pprof for profiling
import _ "net/http/pprof"

func main() {
    go func() {
        log.Println(http.ListenAndServe("localhost:6060", nil))
    }()
    
    // Application code
}
```

```bash
# CPU profile
go tool pprof http://localhost:6060/debug/pprof/profile?seconds=30

# Memory profile
go tool pprof http://localhost:6060/debug/pprof/heap

# Goroutine profile
go tool pprof http://localhost:6060/debug/pprof/goroutine
```

### Benchmarking

```go
// GOOD: Benchmark tests
func BenchmarkGetUser(b *testing.B) {
    repo := setupTestRepo(b)
    ctx := context.Background()
    
    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        _, err := repo.Get(ctx, 1)
        if err != nil {
            b.Fatal(err)
        }
    }
}
```

```bash
# Run benchmarks
go test -bench=. -benchmem

# Compare benchmarks
go test -bench=. -count=10 > old.txt
# Make changes
go test -bench=. -count=10 > new.txt
benchstat old.txt new.txt
```

### Optimization Tips

```go
// GOOD: Pre-allocate slices when size is known
users := make([]*model.User, 0, expectedCount)  // ✅
for _, id := range ids {
    user, _ := repo.Get(ctx, id)
    users = append(users, user)
}

// BAD: Let slice grow dynamically
var users []*model.User  // ❌ Will reallocate
for _, id := range ids {
    user, _ := repo.Get(ctx, id)
    users = append(users, user)
}


// GOOD: Use strings.Builder for string concatenation
var sb strings.Builder
for _, s := range strings {
    sb.WriteString(s)
}
result := sb.String()

// BAD: String concatenation in loop
result := ""
for _, s := range strings {
    result += s  // ❌ Creates new string each iteration
}
```

---

## Best Practices Summary

| ✅ DO | ❌ DON'T |
|---|---|
| Use `gofmt` and `goimports` | Hand-format code |
| Accept interfaces, return structs | Return interfaces |
| Handle errors explicitly | Ignore errors with `_` |
| Pass `context.Context` as first parameter | Use bare functions without context |
| Use goroutines for concurrent work | Use shared memory without sync |
| Use channels for communication | Share memory between goroutines |
| Keep interfaces small and focused | Create large interfaces |
| Use structured logging (zap) | Use `fmt.Println` for logging |
| Use parameterized SQL queries | Concatenate SQL strings |
| Use transactions for related operations | Make multiple non-transactional writes |
| Use `errgroup` for concurrent errors | Manually manage goroutine errors |
| Write table-driven tests | Write repetitive test code |
| Use `t.Helper()` in test helpers | Skip helper functions |
| Profile before optimizing | Guess at bottlenecks |
| Return errors, don't panic | Panic for normal control flow |

---

## References

- [Effective Go](https://go.dev/doc/effective_go)
- [Go Code Review Comments](https://github.com/golang/go/wiki/CodeReviewComments)
- [Go by Example](https://gobyexample.com/)
- [Uber Go Style Guide](https://github.com/uber-go/guide/blob/master/style.md)
- [Go Proverbs](https://go-proverbs.github.io/)
- [golangci-lint](https://golangci-lint.run/)
- [pkg.go.dev](https://pkg.go.dev/)
- [Go Database/SQL Tutorial](http://go-database-sql.org/)
