# Packaging Engineering Standards

> Building, versioning, and distributing MyWorld Central Portal.

## Table of Contents

1. [Semantic Versioning](#semantic-versioning)
2. [Build Artifacts](#build-artifacts)
3. [Container Packaging](#container-packaging)
4. [Library Packaging (Python)](#library-packaging-python)
5. [Library Packaging (TypeScript)](#library-packaging-typescript)
6. [Release Process](#release-process)
7. [Distribution Channels](#distribution-channels)
8. [Software Bill of Materials (SBOM)](#software-bill-of-materials-sbom)
9. [Changelog](#changelog)

---

## Semantic Versioning

### Version Format: MAJOR.MINOR.PATCH

```
1.0.0
│ │ │
│ │ └─ PATCH: Bug fixes, no breaking changes
│ └─── MINOR: New features, backward compatible
└───── MAJOR: Breaking changes
```

### Pre-release Identifiers

```
1.0.0-alpha.1      # Alpha release
1.0.0-beta.2       # Beta release
1.0.0-rc.1         # Release candidate
1.0.0              # Stable release
```

### When to Bump

| Change Type | Version Bump | Example |
|-------------|--------------|---------|
| **Bug fix** | PATCH | 1.0.0 → 1.0.1 |
| **New feature (backward compatible)** | MINOR | 1.0.0 → 1.1.0 |
| **Breaking change** | MAJOR | 1.0.0 → 2.0.0 |
| **Security fix** | PATCH (urgent) | 1.0.0 → 1.0.2 |
| **Deprecate feature** | MINOR (with MAJOR removal next) | 1.0.0 → 1.1.0 |

### Breaking Changes

Examples of breaking changes:
- Removing a public API endpoint
- Changing required request fields
- Changing response format
- Removing/renaming database columns
- Changing authentication mechanism
- Removing a feature

---

## Build Artifacts

### Build Pipeline

```
Source Code (Git)
    ↓
Compile/Lint/Test
    ↓
Build Artifacts
    ├── Docker image (tagged)
    ├── Python wheel (.whl)
    ├── npm package (.tgz)
    └── Source maps
    ↓
Security Scanning
    ↓
Push to Registry
    ↓
Deploy to Environment
```

### CI/CD Build (GitHub Actions)

```yaml
# .github/workflows/build.yml
name: Build and Publish

on:
  push:
    branches: [main, develop]
    tags: ['v*']

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Run tests
        run: |
          pnpm install --frozen-lockfile
          pnpm test
          pnpm lint
          pnpm typecheck
      
      - name: Run security audit
        run: pnpm audit --audit-level moderate

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main' || startsWith(github.ref, 'refs/tags/v')
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Get version
        id: version
        run: |
          if [[ ${{ github.ref }} == refs/tags/v* ]]; then
            echo "version=${GITHUB_REF#refs/tags/v}" >> $GITHUB_OUTPUT
          else
            echo "version=$(date +%Y%m%d)-${GITHUB_SHA::7}" >> $GITHUB_OUTPUT
          fi
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Login to ECR
        uses: aws-actions/amazon-ecr-login@v2
      
      - name: Build and push Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: |
            123456789.dkr.ecr.us-east-1.amazonaws.com/myworld-api:${{ steps.version.outputs.version }}
            123456789.dkr.ecr.us-east-1.amazonaws.com/myworld-api:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max
          provenance: true
          sbom: true
      
      - name: Generate SBOM
        run: |
          curl -sfL https://raw.githubusercontent.com/CycloneDX/cyclonedx-python/main/install.sh | bash -s -- -i /usr/local/bin
          cyclonedx-py -o /tmp/sbom.json
      
      - name: Upload SBOM
        uses: actions/upload-artifact@v4
        with:
          name: sbom
          path: /tmp/sbom.json
```

---

## Container Packaging

### Multi-Stage Build (Already covered in infrastructure/docker.md)

```dockerfile
# GOOD: Multi-stage, minimal final image
FROM python:3.12-slim AS builder
# ... build dependencies
FROM python:3.12-slim AS runtime
# ... runtime only
```

### Image Tagging Strategy

```bash
# Build with multiple tags
docker build -t myworld-api:1.0.0 \
             -t myworld-api:1.0 \
             -t myworld-api:1 \
             -t myworld-api:latest \
             -t 123456789.dkr.ecr.us-east-1.amazonaws.com/myworld-api:1.0.0 \
             -t 123456789.dkr.ecr.us-east-1.amazonaws.com/myworld-api:1.0 \
             -t 123456789.dkr.ecr.us-east-1.amazonaws.com/myworld-api:latest \
             .
```

### Image Labels

```dockerfile
# Add metadata via labels
LABEL org.opencontainers.image.title="MyWorld API"
LABEL org.opencontainers.image.description="MyWorld Central Portal API"
LABEL org.opencontainers.image.version="1.0.0"
LABEL org.opencontainers.image.created="2026-08-30T00:00:00Z"
LABEL org.opencontainers.image.source="https://github.com/myworld/api"
LABEL org.opencontainers.image.licenses="Proprietary"
LABEL org.opencontainers.image.vendor="MyWorld Inc."
```

---

## Library Packaging (Python)

### pyproject.toml (Modern Python Packaging)

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"


[project]
name = "myworld-api"
version = "1.0.0"
description = "MyWorld Central Portal API"
readme = "README.md"
requires-python = ">=3.12"
license = {text = "Proprietary"}
authors = [
    {name = "MyWorld Team", email = "dev@myworld.com"},
]
keywords = ["api", "myworld", "portal"]
classifiers = [
    "Development Status :: 5 - Production/Stable",
    "Framework :: FastAPI",
    "Programming Language :: Python :: 3.12",
    "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
]

dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "pydantic>=2.8.0",
    "pydantic-settings>=2.4.0",
    "sqlalchemy[asyncio]>=2.0.0",
    "asyncpg>=0.29.0",
    "alembic>=1.13.0",
    "redis[hiredis]>=5.0.0",
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=5.0.0",
    "httpx>=0.27.0",
    "mypy>=1.10.0",
    "ruff>=0.5.0",
    "black>=24.0.0",
]
test = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.27.0",
]


[project.urls]
Homepage = "https://myworld.com"
Repository = "https://github.com/myworld/api"
Documentation = "https://docs.myworld.com"
Changelog = "https://github.com/myworld/api/blob/main/CHANGELOG.md"


[tool.setuptools.packages.find]
where = ["src"]
include = ["myworld*"]


[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
addopts = "--cov=myworld --cov-report=term-missing"


[tool.ruff]
line-length = 100
target-version = "py312"


[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "A", "C4", "PT", "RUF"]
ignore = ["E501"]


[tool.mypy]
python_version = "3.12"
strict = true
warn_unused_ignores = true
disallow_untyped_defs = true
```

### Building and Publishing

```bash
# Build wheel and source distribution
python -m build

# Output in dist/
# dist/
# ├── myworld_api-1.0.0-py3-none-any.whl
# └── myworld-api-1.0.0.tar.gz

# Publish to private PyPI
python -m twine upload --repository pypi dist/*

# Or publish to GitHub Packages
python -m twine upload --repository github dist/*
```

### Internal Package Index (AWS CodeArtifact)

```bash
# Configure pip to use CodeArtifact
aws codeartifact get-authorization-token \
    --domain myworld \
    --domain-owner 123456789 \
    --query authorizationToken \
    --output text | docker login --username aws --password-stdin \
    https://myworld-123456789.d.codeartifact.us-east-1.amazonaws.com/pypi/myworld-pypi/simple/

# Configure pip
pip config set global.index-url https://myworld-123456789.d.codeartifact.us-east-1.amazonaws.com/pypi/myworld-pypi/simple/
```

---

## Library Packaging (TypeScript)

### package.json

```json
{
  "name": "@myworld/ui-components",
  "version": "1.0.0",
  "description": "MyWorld shared UI component library",
  "main": "./dist/index.js",
  "module": "./dist/index.mjs",
  "types": "./dist/index.d.ts",
  "exports": {
    ".": {
      "types": "./dist/index.d.ts",
      "import": "./dist/index.mjs",
      "require": "./dist/index.js"
    }
  },
  "files": [
    "dist",
    "README.md",
    "LICENSE"
  ],
  "scripts": {
    "build": "tsup",
    "dev": "tsup --watch",
    "test": "vitest run",
    "lint": "eslint src --ext .ts,.tsx",
    "typecheck": "tsc --noEmit",
    "prepublishOnly": "pnpm build && pnpm test"
  },
  "keywords": ["ui", "components", "react"],
  "license": "UNLICENSED",
  "repository": {
    "type": "git",
    "url": "https://github.com/myworld/ui-components"
  },
  "peerDependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "typescript": "^5.5.0",
    "tsup": "^8.0.0",
    "vitest": "^2.0.0"
  },
  "publishConfig": {
    "registry": "https://npm.pkg.github.com"
  }
}
```

### tsup Configuration

```typescript
// tsup.config.ts
import { defineConfig } from "tsup";

export default defineConfig({
  entry: ["src/index.ts"],
  format: ["cjs", "esm"],
  dts: true,
  sourcemap: true,
  clean: true,
  minify: true,
  splitting: false,
  treeshake: true,
  external: ["react", "react-dom"],
});
```

### Build and Publish

```bash
# Build
pnpm build

# Publish to GitHub Packages
pnpm publish --no-git-checks

# Or to private npm registry
npm publish --registry https://npm.myworld.com
```

---

## Release Process

### Release Workflow

```
1. Feature complete on feature branch
2. Create Pull Request → main
3. CI runs tests, lint, security scan
4. Code review approval (2+ reviewers)
5. Merge to main
6. Automatic: Deploy to staging
7. QA testing on staging
8. Create release tag (v1.0.0)
9. Automatic: Build production artifacts
10. Automatic: Deploy to production
11. Smoke tests on production
12. Update changelog
13. Notify stakeholders
```

### Release Branching Strategy (Trunk-Based)

```bash
# GOOD: Trunk-based with short-lived feature branches
main                           # Always deployable
├── feature/user-export        # Feature branch (max 3 days)
├── feature/dark-mode
└── hotfix/critical-bug        # Direct to main for urgent fixes


# GOOD: Tag releases on main
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0


# GOOD: Use release branches for major versions
release/v2.0                   # Long-lived for major versions
```

### Automated Release (release-please)

```yaml
# .github/workflows/release.yml
name: Release

on:
  push:
    branches: [main]

permissions:
  contents: write
  pull-requests: write

jobs:
  release-please:
    runs-on: ubuntu-latest
    steps:
      - uses: googleapis/release-please-action@v4
        id: release
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          release-type: python  # or node
          package-name: myworld-api
          bump-minor-pre-major: true
          bump-patch-for-minor-pre-major: true
      
      - name: Deploy to production
        if: ${{ steps.release.outputs.release_created }}
        run: |
          echo "Deploying ${{ steps.release.outputs.tag_name }} to production"
          # Trigger deployment
```

---

## Distribution Channels

### Container Registry (AWS ECR)

```bash
# Create ECR repository
aws ecr create-repository \
    --repository-name myworld-api \
    --image-scanning-configuration scanOnPush=true \
    --encryption-configuration encryptionType=KMS

# Lifecycle policy: Keep last 30 images
aws ecr put-lifecycle-policy \
    --repository-name myworld-api \
    --lifecycle-policy-text '{
        "rules": [{
            "rulePriority": 1,
            "description": "Keep last 30 images",
            "selection": {
                "tagStatus": "any",
                "countType": "imageCountMoreThan",
                "countNumber": 30
            },
            "action": {"type": "expire"}
        }]
    }'
```

### Package Registries

| Package Type | Registry | Purpose |
|--------------|----------|---------|
| Python | AWS CodeArtifact | Internal Python packages |
| TypeScript | GitHub Packages / Verdaccio | Internal npm packages |
| Docker | AWS ECR | Container images |
| Helm charts | AWS ECR / GitHub Pages | Kubernetes deployments |
| Terraform modules | GitHub | IaC modules |

---

## Software Bill of Materials (SBOM)

### What is SBOM?

A complete inventory of all components, libraries, and dependencies in your software. Required for:
- Security vulnerability tracking
- License compliance
- Supply chain transparency

### Generate SBOM (CycloneDX)

```bash
# Python
pip install cyclonedx-bom
cyclonedx-py -o sbom.json

# Node.js
npm install -g @cyclonedx/cyclonedx-npm
cyclonedx-npm --output-file sbom.json

# Docker (using syft)
syft 123456789.dkr.ecr.us-east-1.amazonaws.com/myworld-api:1.0.0 -o cyclonedx-json=sbom.json
```

### SBOM in CI/CD

```yaml
- name: Generate SBOM
  run: |
    syft . -o cyclonedx-json > sbom.json
    
- name: Upload SBOM to dependency tracking
  uses: dependency-submission-action@v4
  with:
    artifacts: sbom.json
```

---

## Changelog

### Keep a Changelog Format

```markdown
# Changelog

All notable changes to MyWorld API will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- New dark mode support
- Bulk user import endpoint

### Changed
- Improved error messages for validation failures

### Deprecated
- `GET /users/all` endpoint (use `GET /users?limit=1000` instead)

### Removed

### Fixed
- Fixed race condition in rate limiter
- Fixed N+1 query in user list endpoint

### Security
- Updated bcrypt to 4.2.0 (CVE-2024-XXXX)

## [1.1.0] - 2026-08-15

### Added
- New `/users/{id}/posts` endpoint
- Rate limiting middleware
- Support for 2FA (TOTP)

### Changed
- Upgraded FastAPI from 0.110 to 0.115
- Improved API documentation

### Fixed
- Memory leak in long-running connections

## [1.0.0] - 2026-07-01

### Added
- Initial release
- User authentication and authorization
- CRUD operations for users, posts, comments
```

### Conventional Commits (for Auto-Changelog)

```bash
# Format: <type>(<scope>): <subject>

# Types:
feat:     # New feature (MINOR bump)
fix:      # Bug fix (PATCH bump)
docs:     # Documentation only
style:    # Formatting, no code change
refactor: # Code change that neither fixes bug nor adds feature
perf:     # Performance improvement
test:     # Adding tests
chore:    # Build process or auxiliary tools
BREAKING CHANGE: # Breaking change (MAJOR bump)

# Examples:
git commit -m "feat(users): add bulk import endpoint"
git commit -m "fix(auth): resolve JWT expiration race condition"
git commit -m "perf(api): add Redis caching for user lookups"
git commit -m "feat(api)!: change error response format

BREAKING CHANGE: Error responses now use {'error': {...}} instead of {'detail': '...'}"
```

---

## Best Practices Summary

| ✅ DO | ❌ DON'T |
|---|---|
| Use semantic versioning | Use arbitrary version numbers |
| Tag releases in Git | Forget to tag releases |
| Generate SBOMs | Ship without dependency inventory |
| Sign container images | Push unsigned images |
| Pin dependency versions | Use floating versions in production |
| Write changelogs | Rely on git log alone |
| Use multi-stage Docker builds | Include build tools in final image |
| Scan images for vulnerabilities | Deploy unscanned images |
| Use private registries for internal packages | Publish internal code to public npm/PyPI |
| Include build metadata in images | Build without provenance |
| Test release process in staging | Test release in production |
| Use release branches for major versions | Develop on main without strategy |
| Automate release process | Manual deployments |

---

## References

- [Semantic Versioning](https://semver.org/)
- [Keep a Changelog](https://keepachangelog.com/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [CycloneDX SBOM](https://cyclonedx.org/)
- [AWS CodeArtifact](https://aws.amazon.com/codeartifact/)
- [Trunk-Based Development](https://trunkbaseddevelopment.com/)
- [Docker Image Best Practices](https://docs.docker.com/develop/dev-best-practices/)
