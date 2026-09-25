"""
Tech Stack Config Schema - Configuration for any technology in the stack.

Each technology can have multiple config items:
- ports: network ports
- env: environment variables
- volumes: persistent storage paths
- secrets: sensitive values (passwords, keys)
- resources: CPU/memory limits
- replicas: scaling

Each config item has:
- A default (recommended) value
- Description
- Whether it's required
- Whether it can be customized by the user
- Validation rules
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class ConfigItem:
    """A single config item for a technology"""
    key: str                      # e.g., "port", "DATABASE_URL", "max_connections"
    name: str                     # Human-readable name
    description: str              # What this config is for
    config_type: str              # "port", "env", "volume", "secret", "resource", "replica", "string", "int", "bool"
    default_value: Any            # Recommended default
    required: bool = True
    customizable: bool = True     # Can user override this?
    secret: bool = False          # Is this a secret (should be masked)?
    min_value: Optional[Any] = None   # For numeric: min
    max_value: Optional[Any] = None   # For numeric: max
    options: Optional[List[Any]] = None  # For enum: list of allowed values
    placeholder: str = ""         # For input prompt
    example: str = ""             # Example value
    
    def format_prompt(self) -> str:
        """Format a prompt for the user to confirm/customize this config"""
        secret_marker = " 🔒" if self.secret else ""
        default_str = "***" if self.secret else str(self.default_value)
        
        prompt = f"""
  {self.name}{secret_marker}
  Description: {self.description}
  Default: {default_str}"""
        
        if self.example:
            prompt += f"\n  Example: {self.example}"
        
        if self.min_value is not None or self.max_value is not None:
            range_str = f"[{self.min_value} - {self.max_value}]"
            prompt += f"\n  Range: {range_str}"
        
        if self.options:
            prompt += f"\n  Options: {', '.join(str(o) for o in self.options)}"
        
        if self.customizable:
            prompt += f"\n  → Press Enter for default, or type custom value:"
        else:
            prompt += f"\n  → (Fixed value, cannot be customized)"
        
        return prompt


@dataclass
class ServiceOption:
    """A single service option within a category"""
    name: str                     # e.g., "PostgreSQL"
    key: str                      # e.g., "postgresql"
    default_port: int             # e.g., 5432 (for quick reference)
    description: str              # e.g., "Advanced open-source relational database"
    recommended: bool             # Is this the recommended default for the category?
    tier: str                     # "standard", "premium", "lightweight", "enterprise"
    notes: str = ""               # Additional notes
    configs: List[ConfigItem] = field(default_factory=list)  # All configs for this option
    
    def get_config(self, key: str) -> Optional[ConfigItem]:
        """Get a config item by key"""
        for cfg in self.configs:
            if cfg.key == key:
                return cfg
        return None
    
    def get_required_configs(self) -> List[ConfigItem]:
        """Get all required configs"""
        return [c for c in self.configs if c.required]
    
    def get_customizable_configs(self) -> List[ConfigItem]:
        """Get all configs user can customize"""
        return [c for c in self.configs if c.customizable]


@dataclass
class ServiceCategory:
    """A category of services (database, cache, etc.)"""
    name: str                     # e.g., "Database"
    key: str                      # e.g., "database"
    description: str              # e.g., "Primary data store for the application"
    required: bool                # Is this required?
    options: List[ServiceOption] = field(default_factory=list)
    default_option_key: Optional[str] = None
    
    def get_recommended(self) -> Optional[ServiceOption]:
        for opt in self.options:
            if opt.recommended:
                return opt
        return self.options[0] if self.options else None
    
    def find_option(self, key: str) -> Optional[ServiceOption]:
        for opt in self.options:
            if opt.key == key:
                return opt
        return None


# Helper: Standard config items reused across services
def port_config(internal: int, name: str = "Port", 
                description: str = "Network port") -> ConfigItem:
    return ConfigItem(
        key="port",
        name=name,
        description=description,
        config_type="port",
        default_value=internal,
        required=True,
        customizable=True,
        min_value=1024,
        max_value=65535,
        example=str(internal)
    )


def env_config(key: str, default: Any, description: str, 
               secret: bool = False, required: bool = True) -> ConfigItem:
    return ConfigItem(
        key=f"env:{key}",
        name=f"ENV: {key}",
        description=description,
        config_type="env",
        default_value=default,
        required=required,
        customizable=True,
        secret=secret
    )


def secret_config(key: str, default: str, description: str) -> ConfigItem:
    return ConfigItem(
        key=f"secret:{key}",
        name=f"SECRET: {key}",
        description=description,
        config_type="secret",
        default_value=default,
        required=True,
        customizable=True,
        secret=True,
        placeholder="enter secret value (will be masked)"
    )


def volume_config(path: str, size: str = "1Gi") -> ConfigItem:
    return ConfigItem(
        key=f"volume:{path}",
        name=f"VOLUME: {path}",
        description=f"Persistent storage at {path}",
        config_type="volume",
        default_value=size,
        required=False,
        customizable=True
    )


def resource_config(cpu: str, memory: str) -> List[ConfigItem]:
    return [
        ConfigItem(
            key="resource:cpu",
            name="CPU Limit",
            description="CPU limit (e.g., '500m', '1.0')",
            config_type="resource",
            default_value=cpu,
            required=False,
            customizable=True
        ),
        ConfigItem(
            key="resource:memory",
            name="Memory Limit",
            description="Memory limit (e.g., '512Mi', '1Gi')",
            config_type="resource",
            default_value=memory,
            required=False,
            customizable=True
        ),
    ]


# ============ BUILD THE CATALOG WITH FULL CONFIGS ============

SERVICE_CATALOG: Dict[str, ServiceCategory] = {
    # ============ FRONTEND ============
    "web": ServiceCategory(
        key="web",
        name="Web Frontend",
        description="The web application frontend",
        required=True,
        options=[
            ServiceOption(
                "Next.js", "next.js", 3000, "React framework with SSR/SSG", True, "standard",
                configs=[
                    port_config(3000, "Web Port", "Port for the web application"),
                    env_config("NODE_ENV", "production", "Node environment"),
                    env_config("NEXT_PUBLIC_API_URL", "http://localhost:8000", "Backend API URL (public)"),
                    env_config("NEXT_PUBLIC_APP_NAME", "MyApp", "Application name"),
                ]
            ),
            ServiceOption(
                "React (Vite)", "react", 5173, "Fast React dev server with Vite", False, "standard",
                configs=[
                    port_config(5173, "Web Port", "Port for Vite dev server"),
                    env_config("VITE_API_URL", "http://localhost:8000", "Backend API URL"),
                ]
            ),
            ServiceOption(
                "Vue 3", "vue", 5173, "Progressive JavaScript framework", False, "standard",
                configs=[
                    port_config(5173, "Web Port", "Port for Vite dev server"),
                    env_config("VITE_API_URL", "http://localhost:8000", "Backend API URL"),
                ]
            ),
            ServiceOption(
                "Angular", "angular", 4200, "Full-featured TypeScript framework", False, "standard",
                configs=[
                    port_config(4200, "Web Port", "Port for Angular dev server"),
                    env_config("API_URL", "http://localhost:8000", "Backend API URL"),
                ]
            ),
        ],
        default_option_key="next.js",
    ),
    
    "mobile": ServiceCategory(
        key="mobile",
        name="Mobile Frontend",
        description="The mobile application",
        required=False,
        options=[
            ServiceOption(
                "React Native", "react-native", 8081, "Native mobile with JavaScript", True, "standard",
                configs=[
                    port_config(8081, "Metro Port", "Metro bundler port"),
                    env_config("API_URL", "http://localhost:8000", "Backend API URL"),
                ]
            ),
            ServiceOption(
                "Expo", "expo", 19000, "Managed React Native workflow", False, "standard",
                configs=[
                    port_config(19000, "Expo Dev Port", "Expo dev server port"),
                    env_config("EXPO_PUBLIC_API_URL", "http://localhost:8000", "Backend API URL"),
                ]
            ),
            ServiceOption(
                "Flutter", "flutter", 0, "Cross-platform with Dart", False, "standard",
                configs=[
                    env_config("API_URL", "http://localhost:8000", "Backend API URL"),
                ]
            ),
            ServiceOption(
                "No Mobile", "none", 0, "Skip mobile development", False, "none", configs=[]
            ),
        ],
        default_option_key="react-native",
    ),
    
    # ============ BACKEND ============
    "api": ServiceCategory(
        key="api",
        name="API Backend",
        description="The application backend/API server",
        required=True,
        options=[
            ServiceOption(
                "FastAPI", "fastapi", 8000, "Modern, fast Python API with async", True, "standard",
                configs=[
                    port_config(8000, "API Port", "Port for the API server"),
                    env_config("API_HOST", "0.0.0.0", "API bind host"),
                    env_config("API_WORKERS", 4, "Number of workers"),
                    env_config("LOG_LEVEL", "INFO", "Logging level"),
                    env_config("CORS_ORIGINS", '["http://localhost:3000"]', "Allowed CORS origins"),
                    env_config("RATE_LIMIT_PER_MINUTE", 60, "Rate limit per minute"),
                    secret_config("JWT_SECRET_KEY", "change-me-in-production", "JWT signing secret"),
                ]
            ),
            ServiceOption(
                "Flask", "flask", 5000, "Lightweight Python web framework", False, "lightweight",
                configs=[
                    port_config(5000, "API Port", "Port for Flask"),
                    env_config("FLASK_ENV", "production", "Flask environment"),
                    env_config("FLASK_DEBUG", False, "Debug mode"),
                ]
            ),
            ServiceOption(
                "Django", "django", 8000, "Full-featured Python framework", False, "standard",
                configs=[
                    port_config(8000, "Django Port", "Port for Django dev server"),
                    env_config("DJANGO_SETTINGS_MODULE", "config.settings", "Settings module"),
                    env_config("ALLOWED_HOSTS", "localhost,127.0.0.1", "Allowed hosts"),
                    secret_config("DJANGO_SECRET_KEY", "change-me", "Django secret key"),
                ]
            ),
            ServiceOption(
                "Express.js", "express", 3000, "Minimal Node.js framework", False, "standard",
                configs=[
                    port_config(3000, "API Port", "Port for Express"),
                    env_config("NODE_ENV", "production", "Node environment"),
                    env_config("PORT", 3000, "Server port"),
                ]
            ),
            ServiceOption(
                "NestJS", "nestjs", 3000, "TypeScript-first Node.js framework", False, "standard",
                configs=[
                    port_config(3000, "API Port", "Port for NestJS"),
                    env_config("NODE_ENV", "production", "Node environment"),
                ]
            ),
            ServiceOption(
                "Spring Boot", "spring", 8080, "Enterprise Java framework", False, "enterprise",
                configs=[
                    port_config(8080, "API Port", "Port for Spring Boot"),
                    env_config("SPRING_PROFILES_ACTIVE", "prod", "Active Spring profile"),
                    env_config("SERVER_PORT", 8080, "Server port"),
                ]
            ),
            ServiceOption(
                "Gin (Go)", "gin", 8080, "Fast Go web framework", False, "standard",
                configs=[
                    port_config(8080, "API Port", "Port for Gin"),
                    env_config("GIN_MODE", "release", "Gin mode (debug/release/test)"),
                ]
            ),
        ],
        default_option_key="fastapi",
    ),
    
    # ============ DATABASES ============
    "database": ServiceCategory(
        key="database",
        name="Primary Database",
        description="Main data store for the application",
        required=True,
        options=[
            ServiceOption(
                "PostgreSQL", "postgresql", 5432, "Advanced open-source relational DB", True, "standard",
                configs=[
                    port_config(5432, "Postgres Port", "Port for PostgreSQL"),
                    env_config("POSTGRES_USER", "appuser", "Database user"),
                    env_config("POSTGRES_PASSWORD", "change-me-in-production", "Database password", secret=True),
                    env_config("POSTGRES_DB", "appdb", "Database name"),
                    env_config("POSTGRES_HOST", "postgres", "Database host (in Docker)"),
                    env_config("POSTGRES_MAX_CONNECTIONS", 100, "Max connections"),
                    env_config("POSTGRES_SHARED_BUFFERS", "256MB", "Shared buffers"),
                    volume_config("/var/lib/postgresql/data", "10Gi"),
                ]
            ),
            ServiceOption(
                "PostgreSQL + pgvector", "postgresql-pgvector", 5432, "PostgreSQL with vector search", False, "standard",
                "Use for AI/ML applications needing similarity search",
                configs=[
                    port_config(5432, "Postgres Port", "Port for PostgreSQL"),
                    env_config("POSTGRES_USER", "appuser", "Database user"),
                    env_config("POSTGRES_PASSWORD", "change-me-in-production", "Database password", secret=True),
                    env_config("POSTGRES_DB", "appdb", "Database name"),
                    env_config("POSTGRES_HOST", "postgres", "Database host (in Docker)"),
                    volume_config("/var/lib/postgresql/data", "10Gi"),
                ]
            ),
            ServiceOption(
                "MySQL", "mysql", 3306, "Popular open-source relational DB", False, "standard",
                configs=[
                    port_config(3306, "MySQL Port", "Port for MySQL"),
                    env_config("MYSQL_ROOT_PASSWORD", "change-me", "Root password", secret=True),
                    env_config("MYSQL_DATABASE", "appdb", "Database name"),
                    env_config("MYSQL_USER", "appuser", "Database user"),
                    env_config("MYSQL_PASSWORD", "change-me", "Database password", secret=True),
                    volume_config("/var/lib/mysql", "10Gi"),
                ]
            ),
            ServiceOption(
                "MariaDB", "mariadb", 3306, "MySQL-compatible, community-driven", False, "standard",
                configs=[
                    port_config(3306, "MariaDB Port", "Port for MariaDB"),
                    env_config("MARIADB_ROOT_PASSWORD", "change-me", "Root password", secret=True),
                    env_config("MARIADB_DATABASE", "appdb", "Database name"),
                    env_config("MARIADB_USER", "appuser", "Database user"),
                    env_config("MARIADB_PASSWORD", "change-me", "Database password", secret=True),
                    volume_config("/var/lib/mysql", "10Gi"),
                ]
            ),
            ServiceOption(
                "MongoDB", "mongodb", 27017, "Document-oriented NoSQL", False, "standard",
                "Use for unstructured/flexible schema data",
                configs=[
                    port_config(27017, "MongoDB Port", "Port for MongoDB"),
                    env_config("MONGO_INITDB_ROOT_USERNAME", "root", "Root username"),
                    env_config("MONGO_INITDB_ROOT_PASSWORD", "change-me", "Root password", secret=True),
                    env_config("MONGO_INITDB_DATABASE", "appdb", "Database name"),
                    volume_config("/data/db", "10Gi"),
                ]
            ),
            ServiceOption(
                "SQLite", "sqlite", 0, "Embedded file-based DB", False, "lightweight",
                "Use for small apps, prototypes, edge devices",
                configs=[
                    env_config("SQLITE_PATH", "/data/app.db", "Database file path"),
                    volume_config("/data", "1Gi"),
                ]
            ),
            ServiceOption(
                "ClickHouse", "clickhouse", 8123, "Column-oriented analytics DB", False, "premium",
                "Use for analytics, time-series, OLAP",
                configs=[
                    port_config(8123, "ClickHouse HTTP", "ClickHouse HTTP port"),
                    port_config(9000, "ClickHouse TCP", "ClickHouse TCP port"),
                    env_config("CLICKHOUSE_USER", "default", "User"),
                    env_config("CLICKHOUSE_PASSWORD", "change-me", "Password", secret=True),
                    env_config("CLICKHOUSE_DB", "default", "Default database"),
                    volume_config("/var/lib/clickhouse", "50Gi"),
                ]
            ),
        ],
        default_option_key="postgresql",
    ),
    
    # ============ CACHE ============
    "cache": ServiceCategory(
        key="cache",
        name="Cache Layer",
        description="In-memory cache for performance",
        required=False,
        options=[
            ServiceOption(
                "Redis", "redis", 6379, "In-memory data store with persistence", True, "standard",
                configs=[
                    port_config(6379, "Redis Port", "Port for Redis"),
                    env_config("REDIS_PASSWORD", "change-me-in-production", "Redis password", secret=False),
                    env_config("REDIS_MAXMEMORY", "256mb", "Max memory"),
                    env_config("REDIS_MAXMEMORY_POLICY", "allkeys-lru", "Eviction policy"),
                    volume_config("/data", "2Gi"),
                ]
            ),
            ServiceOption(
                "Memcached", "memcached", 11211, "Distributed memory caching", False, "lightweight",
                configs=[
                    port_config(11211, "Memcached Port", "Port for Memcached"),
                    env_config("MEMCACHED_MEMORY", 64, "Memory in MB"),
                ]
            ),
            ServiceOption(
                "No Cache", "none", 0, "Skip cache layer", False, "none", configs=[]
            ),
        ],
        default_option_key="redis",
    ),
    
    # ============ SEARCH ============
    "search": ServiceCategory(
        key="search",
        name="Search Engine",
        description="Full-text search capability",
        required=False,
        options=[
            ServiceOption(
                "PostgreSQL FTS", "postgresql-fts", 5432, "Built-in PostgreSQL full-text search", True, "lightweight",
                "Use for simple search, no extra service needed",
                configs=[]  # Uses database
            ),
            ServiceOption(
                "Meilisearch", "meilisearch", 7700, "Fast, typo-tolerant search", False, "standard",
                configs=[
                    port_config(7700, "Meilisearch Port", "Port for Meilisearch"),
                    env_config("MEILI_ENV", "production", "Environment"),
                    env_config("MEILI_NO_ANALYTICS", True, "Disable analytics"),
                    env_config("MEILI_MASTER_KEY", "change-me", "Master key", secret=True),
                    volume_config("/meili_data", "5Gi"),
                ]
            ),
            ServiceOption(
                "Elasticsearch", "elasticsearch", 9200, "Distributed search and analytics", False, "enterprise",
                configs=[
                    port_config(9200, "Elasticsearch Port", "Port for Elasticsearch"),
                    env_config("ES_JAVA_OPTS", "-Xms512m -Xmx512m", "JVM options"),
                    env_config("discovery.type", "single-node", "Discovery type"),
                    env_config("xpack.security.enabled", False, "Security enabled"),
                    volume_config("/usr/share/elasticsearch/data", "20Gi"),
                ]
            ),
            ServiceOption(
                "Typesense", "typesense", 8108, "Typo-tolerant search, Algolia alt", False, "standard",
                configs=[
                    port_config(8108, "Typesense Port", "Port for Typesense"),
                    env_config("TYPESENSE_API_KEY", "change-me", "API key", secret=True),
                    volume_config("/data", "5Gi"),
                ]
            ),
            ServiceOption(
                "No Search", "none", 0, "Skip search engine", False, "none", configs=[]
            ),
        ],
        default_option_key="postgresql-fts",
    ),
    
    # ============ MESSAGE QUEUE ============
    "queue": ServiceCategory(
        key="queue",
        name="Message Queue",
        description="Async task/message processing",
        required=False,
        options=[
            ServiceOption(
                "Redis Streams", "redis-streams", 6379, "Queue using Redis (already in cache)", True, "lightweight",
                "Use if Redis is already your cache",
                configs=[]  # Uses cache
            ),
            ServiceOption(
                "RabbitMQ", "rabbitmq", 5672, "Traditional message broker", False, "standard",
                configs=[
                    port_config(5672, "RabbitMQ AMQP", "AMQP port"),
                    port_config(15672, "RabbitMQ Management", "Management UI port"),
                    env_config("RABBITMQ_USER", "guest", "Default user"),
                    env_config("RABBITMQ_PASSWORD", "change-me", "Password", secret=True),
                    env_config("RABBITMQ_VHOST", "/", "Virtual host"),
                    volume_config("/var/lib/rabbitmq", "5Gi"),
                ]
            ),
            ServiceOption(
                "Apache Kafka", "kafka", 9092, "Distributed event streaming", False, "enterprise",
                configs=[
                    port_config(9092, "Kafka Port", "Kafka broker port"),
                    env_config("KAFKA_NODE_ID", 1, "Node ID"),
                    env_config("KAFKA_PROCESS_ROLES", "broker,controller", "Process roles"),
                    env_config("KAFKA_LISTENERS", "PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093", "Listeners"),
                    env_config("KAFKA_CONTROLLER_LISTENER_NAMES", "CONTROLLER", "Controller listener"),
                    env_config("KAFKA_LOG_RETENTION_HOURS", 168, "Log retention hours"),
                    env_config("KAFKA_NUM_PARTITIONS", 3, "Default partitions"),
                    volume_config("/var/lib/kafka/data", "20Gi"),
                ]
            ),
            ServiceOption(
                "NATS", "nats", 4222, "Lightweight, high-performance messaging", False, "standard",
                configs=[
                    port_config(4222, "NATS Client", "NATS client port"),
                    port_config(8222, "NATS HTTP", "NATS HTTP monitoring port"),
                    env_config("NATS_MAX_PAYLOAD", "1MB", "Max payload size"),
                    volume_config("/data", "1Gi"),
                ]
            ),
            ServiceOption(
                "No Queue", "none", 0, "Skip message queue", False, "none", configs=[]
            ),
        ],
        default_option_key="redis-streams",
    ),
    
    # ============ OBJECT STORAGE ============
    "object_storage": ServiceCategory(
        key="object_storage",
        name="Object Storage",
        description="File/blob storage (S3-compatible)",
        required=False,
        options=[
            ServiceOption(
                "Local filesystem", "local", 0, "Store on local disk", True, "lightweight",
                "Use for development, single-server deployments",
                configs=[
                    env_config("UPLOAD_DIR", "/data/uploads", "Upload directory"),
                    volume_config("/data/uploads", "50Gi"),
                    env_config("MAX_UPLOAD_SIZE", "100MB", "Max upload size"),
                ]
            ),
            ServiceOption(
                "MinIO", "minio", 9000, "Self-hosted S3-compatible", False, "standard",
                "Use for on-prem or private cloud S3",
                configs=[
                    port_config(9000, "MinIO API", "MinIO API port"),
                    port_config(9001, "MinIO Console", "MinIO console port"),
                    env_config("MINIO_ROOT_USER", "minioadmin", "Root user"),
                    env_config("MINIO_ROOT_PASSWORD", "change-me", "Root password", secret=True),
                    env_config("MINIO_BUCKET", "uploads", "Default bucket"),
                    volume_config("/data", "100Gi"),
                ]
            ),
            ServiceOption(
                "AWS S3", "aws-s3", 0, "Amazon S3 (cloud)", False, "premium",
                configs=[
                    env_config("AWS_REGION", "us-east-1", "AWS region"),
                    env_config("AWS_S3_BUCKET", "my-app-uploads", "S3 bucket name"),
                    secret_config("AWS_ACCESS_KEY_ID", "your-key", "AWS access key"),
                    secret_config("AWS_SECRET_ACCESS_KEY", "your-secret", "AWS secret key"),
                    env_config("AWS_S3_ENDPOINT", "", "Custom endpoint (for S3-compatible)"),
                ]
            ),
            ServiceOption(
                "Google Cloud Storage", "gcs", 0, "GCS (cloud)", False, "premium",
                configs=[
                    env_config("GCP_PROJECT_ID", "my-project", "GCP project ID"),
                    env_config("GCS_BUCKET", "my-app-uploads", "GCS bucket name"),
                    env_config("GOOGLE_APPLICATION_CREDENTIALS", "/secrets/gcp-key.json", "Path to service account key"),
                ]
            ),
        ],
        default_option_key="local",
    ),
    
    # ============ AUTH ============
    "auth": ServiceCategory(
        key="auth",
        name="Authentication",
        description="User authentication provider",
        required=False,
        options=[
            ServiceOption(
                "Self-managed (JWT)", "self-jwt", 0, "JWT in your own API", True, "lightweight",
                "Use for simple apps, full control",
                configs=[
                    env_config("JWT_ALGORITHM", "HS256", "JWT algorithm"),
                    env_config("JWT_EXPIRATION_HOURS", 24, "Token expiration in hours"),
                    env_config("JWT_REFRESH_EXPIRATION_DAYS", 30, "Refresh token expiration in days"),
                    secret_config("JWT_SECRET_KEY", "change-me-in-production", "JWT signing secret"),
                    env_config("PASSWORD_MIN_LENGTH", 8, "Min password length"),
                    env_config("REQUIRE_EMAIL_VERIFICATION", True, "Require email verification"),
                ]
            ),
            ServiceOption(
                "Keycloak", "keycloak", 8080, "Self-hosted identity provider", False, "standard",
                "Use for enterprise SSO/SAML",
                configs=[
                    port_config(8080, "Keycloak Port", "Keycloak HTTP port"),
                    env_config("KEYCLOAK_ADMIN", "admin", "Admin user"),
                    env_config("KEYCLOAK_ADMIN_PASSWORD", "change-me", "Admin password", secret=True),
                    env_config("KEYCLOAK_REALM", "myapp", "Default realm"),
                ]
            ),
            ServiceOption(
                "Auth0", "auth0", 0, "Managed auth service (cloud)", False, "premium",
                configs=[
                    env_config("AUTH0_DOMAIN", "your-tenant.auth0.com", "Auth0 domain"),
                    env_config("AUTH0_CLIENT_ID", "your-client-id", "Auth0 client ID"),
                    secret_config("AUTH0_CLIENT_SECRET", "your-secret", "Auth0 client secret"),
                    env_config("AUTH0_AUDIENCE", "https://api.myapp.com", "API audience"),
                ]
            ),
            ServiceOption(
                "Clerk", "clerk", 0, "Modern auth-as-a-service", False, "premium",
                configs=[
                    env_config("CLERK_PUBLISHABLE_KEY", "pk_test_...", "Clerk publishable key"),
                    secret_config("CLERK_SECRET_KEY", "sk_test_...", "Clerk secret key"),
                ]
            ),
            ServiceOption(
                "Supabase Auth", "supabase-auth", 0, "Open-source Firebase alt", False, "premium",
                configs=[
                    env_config("SUPABASE_URL", "https://xxx.supabase.co", "Supabase URL"),
                    env_config("SUPABASE_ANON_KEY", "your-anon-key", "Anon key"),
                    secret_config("SUPABASE_SERVICE_KEY", "your-service-key", "Service key"),
                ]
            ),
            ServiceOption(
                "Google OAuth", "google-oauth", 0, "Sign in with Google", False, "standard",
                configs=[
                    env_config("GOOGLE_CLIENT_ID", "your-client-id", "Google client ID"),
                    secret_config("GOOGLE_CLIENT_SECRET", "your-secret", "Google client secret"),
                    env_config("GOOGLE_REDIRECT_URI", "http://localhost:3000/auth/callback", "OAuth redirect URI"),
                ]
            ),
            ServiceOption(
                "NextAuth.js", "nextauth", 0, "Auth for Next.js apps", False, "lightweight",
                configs=[
                    secret_config("NEXTAUTH_SECRET", "change-me", "NextAuth secret"),
                    env_config("NEXTAUTH_URL", "http://localhost:3000", "NextAuth URL"),
                ]
            ),
        ],
        default_option_key="self-jwt",
    ),
    
    # ============ MONITORING ============
    "monitoring": ServiceCategory(
        key="monitoring",
        name="Monitoring & Observability",
        description="Application monitoring and logging",
        required=False,
        options=[
            ServiceOption(
                "Self-managed logs only", "self-logs", 0, "Just write to local files", True, "lightweight",
                configs=[
                    env_config("LOG_LEVEL", "INFO", "Log level (DEBUG/INFO/WARNING/ERROR)"),
                    env_config("LOG_FORMAT", "json", "Log format (json/text)"),
                    env_config("LOG_FILE", "/var/log/app/app.log", "Log file path"),
                    env_config("LOG_ROTATION", "daily", "Log rotation (daily/weekly/size)"),
                    env_config("LOG_RETENTION_DAYS", 30, "Log retention in days"),
                ]
            ),
            ServiceOption(
                "Prometheus + Grafana", "prometheus", 9090, "Metrics + dashboards", False, "standard",
                configs=[
                    port_config(9090, "Prometheus", "Prometheus port"),
                    port_config(3000, "Grafana", "Grafana port (may conflict with web)"),
                    env_config("PROMETHEUS_RETENTION", "15d", "Metrics retention"),
                    env_config("GRAFANA_ADMIN_USER", "admin", "Grafana admin user"),
                    env_config("GRAFANA_ADMIN_PASSWORD", "change-me", "Grafana admin password", secret=True),
                    volume_config("/prometheus", "20Gi"),
                    volume_config("/var/lib/grafana", "5Gi"),
                ]
            ),
            ServiceOption(
                "Loki + Grafana", "loki", 3100, "Log aggregation", False, "standard",
                configs=[
                    port_config(3100, "Loki", "Loki port"),
                    port_config(3000, "Grafana", "Grafana port"),
                    env_config("LOKI_RETENTION", "30d", "Log retention"),
                    volume_config("/loki", "20Gi"),
                ]
            ),
            ServiceOption(
                "Sentry", "sentry", 9000, "Error tracking and monitoring", False, "premium",
                configs=[
                    port_config(9000, "Sentry", "Sentry port"),
                    env_config("SENTRY_DSN", "your-dsn", "Sentry DSN"),
                    env_config("SENTRY_ENVIRONMENT", "production", "Environment"),
                    env_config("SENTRY_TRACES_SAMPLE_RATE", 0.1, "Trace sample rate (0-1)"),
                ]
            ),
            ServiceOption(
                "No Monitoring", "none", 0, "No monitoring", False, "none", configs=[]
            ),
        ],
        default_option_key="self-logs",
    ),
    
    # ============ ML / AI ============
    "ml_platform": ServiceCategory(
        key="ml_platform",
        name="ML/AI Platform",
        description="Machine learning model serving (if applicable)",
        required=False,
        options=[
            ServiceOption(
                "No ML/AI", "none", 0, "No ML/AI needed", True, "none", configs=[]
            ),
            ServiceOption(
                "OpenAI API", "openai", 0, "GPT models via API (cloud)", False, "premium",
                configs=[
                    env_config("OPENAI_MODEL", "gpt-4", "Model to use"),
                    env_config("OPENAI_MAX_TOKENS", 2000, "Max tokens per request"),
                    env_config("OPENAI_TEMPERATURE", 0.7, "Temperature (0-1)"),
                    secret_config("OPENAI_API_KEY", "sk-...", "OpenAI API key"),
                ]
            ),
            ServiceOption(
                "Anthropic API", "anthropic", 0, "Claude via API (cloud)", False, "premium",
                configs=[
                    env_config("ANTHROPIC_MODEL", "claude-3-opus-20240229", "Model to use"),
                    env_config("ANTHROPIC_MAX_TOKENS", 4000, "Max tokens"),
                    secret_config("ANTHROPIC_API_KEY", "sk-ant-...", "Anthropic API key"),
                ]
            ),
            ServiceOption(
                "Ollama", "ollama", 11434, "Local LLM runner", False, "standard",
                configs=[
                    port_config(11434, "Ollama Port", "Ollama API port"),
                    env_config("OLLAMA_MODEL", "llama2", "Default model"),
                    env_config("OLLAMA_KEEP_ALIVE", "5m", "Model keep-alive duration"),
                    volume_config("/root/.ollama", "50Gi"),
                ]
            ),
            ServiceOption(
                "vLLM", "vllm", 8000, "High-throughput LLM serving", False, "premium",
                configs=[
                    port_config(8000, "vLLM Port", "vLLM API port"),
                    env_config("VLLM_MODEL", "meta-llama/Llama-2-7b", "Model to serve"),
                    env_config("VLLM_MAX_MODEL_LEN", 4096, "Max model length"),
                    env_config("VLLM_GPU_MEMORY_UTILIZATION", 0.9, "GPU memory utilization"),
                ]
            ),
        ],
        default_option_key="none",
    ),
    
    "vector_db": ServiceCategory(
        key="vector_db",
        name="Vector Database",
        description="For AI embeddings and similarity search",
        required=False,
        options=[
            ServiceOption(
                "pgvector (PostgreSQL)", "pgvector", 5432, "PostgreSQL extension", True, "standard",
                "Use if already using PostgreSQL",
                configs=[]
            ),
            ServiceOption(
                "Qdrant", "qdrant", 6333, "Vector DB with filters", False, "standard",
                configs=[
                    port_config(6333, "Qdrant HTTP", "Qdrant HTTP port"),
                    port_config(6334, "Qdrant gRPC", "Qdrant gRPC port"),
                    env_config("QDRANT_API_KEY", "change-me", "API key", secret=True),
                    volume_config("/qdrant/storage", "20Gi"),
                ]
            ),
            ServiceOption(
                "Chroma", "chroma", 8000, "Embeddings database", False, "lightweight",
                configs=[
                    port_config(8000, "Chroma Port", "Chroma port"),
                    env_config("CHROMA_AUTH_TOKEN", "change-me", "Auth token", secret=True),
                    volume_config("/chroma/chroma", "10Gi"),
                ]
            ),
            ServiceOption(
                "Weaviate", "weaviate", 8080, "Vector DB with modules", False, "standard",
                configs=[
                    port_config(8080, "Weaviate Port", "Weaviate port"),
                    env_config("WEAVIATE_API_KEY", "change-me", "API key", secret=True),
                    volume_config("/var/lib/weaviate", "20Gi"),
                ]
            ),
            ServiceOption(
                "No Vector DB", "none", 0, "Not needed", False, "none", configs=[]
            ),
        ],
        default_option_key="pgvector",
    ),
    
    # ============ API GATEWAY ============
    "api_gateway": ServiceCategory(
        key="api_gateway",
        name="API Gateway",
        description="Single entry point for APIs (microservices)",
        required=False,
        options=[
            ServiceOption(
                "No API Gateway", "none", 0, "Direct API access", True, "none",
                "Use for monolith or simple deployments",
                configs=[]
            ),
            ServiceOption(
                "NGINX", "nginx", 80, "Classic reverse proxy", False, "standard",
                configs=[
                    port_config(80, "HTTP Port", "NGINX HTTP port"),
                    port_config(443, "HTTPS Port", "NGINX HTTPS port"),
                    env_config("NGINX_WORKER_PROCESSES", "auto", "Worker processes"),
                    env_config("NGINX_WORKER_CONNECTIONS", 1024, "Worker connections"),
                ]
            ),
            ServiceOption(
                "Traefik", "traefik", 8080, "Modern reverse proxy", False, "standard",
                configs=[
                    port_config(8080, "Traefik Dashboard", "Traefik dashboard port"),
                    port_config(80, "HTTP", "HTTP port"),
                    port_config(443, "HTTPS", "HTTPS port"),
                    env_config("TRAEFIK_LOG_LEVEL", "INFO", "Log level"),
                ]
            ),
            ServiceOption(
                "Caddy", "caddy", 80, "Automatic HTTPS", False, "standard",
                configs=[
                    port_config(80, "HTTP", "HTTP port"),
                    port_config(443, "HTTPS", "HTTPS port"),
                    port_config(2019, "Admin API", "Caddy admin port"),
                ]
            ),
        ],
        default_option_key="none",
    ),
    
    # ============ CI/CD ============
    "ci_cd": ServiceCategory(
        key="ci_cd",
        name="CI/CD Platform",
        description="Continuous Integration / Deployment",
        required=False,
        options=[
            ServiceOption(
                "GitHub Actions", "github-actions", 0, "GitHub-hosted CI/CD", True, "standard",
                configs=[
                    env_config("GITHUB_TOKEN", "", "GitHub token for CI", secret=True),
                    env_config("CI_REGISTRY", "ghcr.io", "Container registry"),
                    env_config("CI_IMAGE_NAME", "myorg/myapp", "Image name"),
                ]
            ),
            ServiceOption(
                "GitLab CI", "gitlab-ci", 0, "GitLab-hosted CI/CD", False, "standard",
                configs=[
                    env_config("GITLAB_TOKEN", "", "GitLab token", secret=True),
                    env_config("CI_REGISTRY_IMAGE", "registry.gitlab.com/myorg/myapp", "Registry image"),
                ]
            ),
            ServiceOption(
                "Jenkins", "jenkins", 8080, "Self-hosted CI/CD", False, "standard",
                configs=[
                    port_config(8080, "Jenkins Port", "Jenkins HTTP port"),
                    env_config("JENKINS_USER", "admin", "Admin user"),
                    env_config("JENKINS_PASSWORD", "change-me", "Admin password", secret=True),
                    volume_config("/var/jenkins_home", "50Gi"),
                ]
            ),
            ServiceOption(
                "No CI/CD", "none", 0, "Manual deployments", False, "none", configs=[]
            ),
        ],
        default_option_key="github-actions",
    ),
}


def get_service_category(key: str) -> Optional[ServiceCategory]:
    return SERVICE_CATALOG.get(key)


def get_all_required_services() -> List[ServiceCategory]:
    return [cat for cat in SERVICE_CATALOG.values() if cat.required]


def get_optional_services() -> List[ServiceCategory]:
    return [cat for cat in SERVICE_CATALOG.values() if not cat.required]


def format_service_question(category: ServiceCategory, 
                            previously_selected: Optional[str] = None) -> str:
    """Format a service selection question for the user"""
    recommended = category.get_recommended()
    
    output = f"""
═══════════════════════════════════════════════════════════════
  {category.name.upper()}
═══════════════════════════════════════════════════════════════

{category.description}

"""
    
    if previously_selected:
        prev_opt = category.find_option(previously_selected)
        if prev_opt:
            output += f"Previously selected: {prev_opt.name} (port {prev_opt.default_port})\n\n"
    
    output += f"OPTIONS:\n"
    for i, opt in enumerate(category.options, 1):
        marker = "★ (Recommended)" if opt.recommended else f"  [{i}]"
        port_info = f":{opt.default_port}" if opt.default_port > 0 else " (no port)"
        output += f"  {marker} {opt.name}{port_info} - {opt.description}\n"
        if opt.notes:
            output += f"      Note: {opt.notes}\n"
        if opt.tier != "standard":
            output += f"      Tier: {opt.tier}\n"
        if opt.configs:
            output += f"      Configs: {len(opt.configs)} configurable items\n"
    
    output += f"""
═══════════════════════════════════════════════════════════════
  Select: [name] | [number] | 'custom <key>:<port>' | 'skip' (optional)
═══════════════════════════════════════════════════════════════
"""
    return output


def parse_service_selection(category: ServiceCategory, 
                             user_input: str) -> Optional[ServiceOption]:
    user_input = user_input.strip().lower()
    if user_input in ("skip", "s", ""):
        return None
    
    if user_input.startswith("custom"):
        parts = user_input.split(":", 1)
        if len(parts) == 2:
            try:
                port = int(parts[0].replace("custom", "").strip())
                tech = parts[1].strip()
                return ServiceOption(
                    name=f"Custom ({tech})",
                    key=tech,
                    default_port=port,
                    description=f"User-specified: {tech} on port {port}",
                    recommended=False,
                    tier="custom",
                    configs=[]  # User will configure
                )
            except ValueError:
                pass
    
    for opt in category.options:
        if opt.name.lower() == user_input or opt.key == user_input:
            return opt
    
    try:
        idx = int(user_input) - 1
        if 0 <= idx < len(category.options):
            return category.options[idx]
    except ValueError:
        pass
    
    return category.get_recommended()


def format_config_questions(option: ServiceOption) -> str:
    """Format questions for each config of a service option"""
    if not option.configs:
        return f"\n{option.name} has no additional configuration (uses defaults).\n"
    
    output = f"""
═══════════════════════════════════════════════════════════════
  CONFIGURATION FOR: {option.name}
═══════════════════════════════════════════════════════════════

Review the following configurations. Press Enter to accept each default,
or type a custom value.
"""
    
    for cfg in option.configs:
        output += cfg.format_prompt()
    
    output += "\n═══════════════════════════════════════════════════════════════\n"
    return output
