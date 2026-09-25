"""
Docker Compose Generator - Generates docker-compose.yml from project-config.json

Uses the dynamic port_config module to derive ports from tech stack.
Ports are NOT hardcoded — they are derived from:
- Tech stack (framework defaults)
- Architecture (services needed)
- Available ports on host
"""

import json
from pathlib import Path
from typing import Dict, Any
from core.port_config import get_port, derive_ports_from_tech_stack, get_default_port


def generate_docker_compose(project_config: Dict[str, Any]) -> str:
    """Generate docker-compose.yml from project config using dynamic ports"""
    project_name = project_config["name"]
    tech_stack = project_config.get("tech_stack_hints", {})
    architecture_services = project_config.get("architecture_services", [])
    
    # Check if we have dynamic port allocations
    ports_config = project_config.get("ports", {})
    
    if isinstance(ports_config, dict) and "allocations" in ports_config:
        # New dynamic format
        allocations = ports_config["allocations"]
        api_port = allocations.get("api", {}).get("external_port", 8000)
        api_internal = allocations.get("api", {}).get("internal_port", 8000)
        web_port = allocations.get("web", {}).get("external_port", 3000)
        web_internal = allocations.get("web", {}).get("internal_port", 3000)
        pg_ext = allocations.get("database", {}).get("external_port", 5433)
        pg_int = allocations.get("database", {}).get("internal_port", 5432)
        redis_ext = allocations.get("cache", {}).get("external_port", 6380)
        redis_int = allocations.get("cache", {}).get("internal_port", 6379)
    else:
        # Derive from tech stack dynamically
        derived = derive_ports_from_tech_stack(tech_stack, architecture_services, check_available=False)
        
        def get_ports(service, default_ext, default_int):
            if service in derived:
                return derived[service].external_port, derived[service].internal_port
            return default_ext, default_int
        
        web_port, web_internal = get_ports("web", 3000, 3000)
        api_port, api_internal = get_ports("api", 8000, 8000)
        pg_ext, pg_int = get_ports("database", 5433, 5432)
        redis_ext, redis_int = get_ports("cache", 6380, 6379)
    
    compose = f"""services:
  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: {project_name}
      POSTGRES_PASSWORD: {project_name}
      POSTGRES_DB: {project_name}
    ports:
      - "{pg_ext}:{pg_int}"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U {project_name} -d {project_name}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    ports:
      - "{redis_ext}:{redis_int}"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 5s

  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    restart: unless-stopped
    ports:
      - "{api_port}:{api_internal}"
    environment:
      DATABASE_URL: postgresql+asyncpg://{project_name}:{project_name}@postgres:{pg_int}/{project_name}
      REDIS_URL: redis://redis:{redis_int}/0
      JWT_SECRET_KEY: ${{JWT_SECRET_KEY:-dev-secret-key-change-in-production}}
      JWT_ALGORITHM: HS256
      GOOGLE_CLIENT_ID: ${{GOOGLE_CLIENT_ID:-}}
      GOOGLE_CLIENT_SECRET: ${{GOOGLE_CLIENT_SECRET:-}}
      GOOGLE_REDIRECT_URI: ${{GOOGLE_REDIRECT_URI:-http://localhost:{web_port}/auth/callback}}
      CORS_ORIGINS: '["http://localhost:{web_port}"]'
      LOG_LEVEL: INFO
      CELERY_BROKER_URL: redis://redis:{redis_int}/1
      CELERY_RESULT_BACKEND: redis://redis:{redis_int}/2
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:{api_internal}/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 15s

  web:
    build:
      context: .
      dockerfile: Dockerfile.web
    restart: unless-stopped
    ports:
      - "{web_port}:{web_internal}"
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:{api_port}/api/v1
      NEXT_PUBLIC_GOOGLE_CLIENT_ID: ${{NEXT_PUBLIC_GOOGLE_CLIENT_ID:-}}
    depends_on:
      api:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:{web_internal}"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 15s

volumes:
  postgres_data:
  redis_data:
"""
    
    return compose


def generate_from_config_file(config_path: str, output_path: str = None) -> str:
    """Generate docker-compose.yml from a project-config.json file"""
    with open(config_path) as f:
        config = json.load(f)
    
    content = generate_docker_compose(config)
    
    if output_path:
        with open(output_path, 'w') as f:
            f.write(content)
    
    return content


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python docker_compose_generator.py <project-config.json> [output-path]")
        sys.exit(1)
    
    config_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    content = generate_from_config_file(config_path, output_path)
    
    if not output_path:
        print(content)
    else:
        print(f"Generated: {output_path}")
