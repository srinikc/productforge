# Packaging Agent Skill

## Purpose
Builds platform-specific packages, installers, and artifacts for the completed software product including BOM, security audits, licenses, and cross-platform packaging.

## Stage
Stage 8: Package (after Document)

## Inputs
- Source code from `products/<project>/src/`
- Documentation from `products/<project>/docs/`
- Test reports from `products/<project>/reports/`
- Project config from `products/<project>/project-config.json`
- Architecture docs from `products/<project>/architecture/`

## Outputs
- `products/<project>/dist/` - Distribution packages
  - For Web: `dist/*-web.zip` (with static assets)
  - For Desktop: `dist/*-win.zip`, `dist/*-mac.zip`, `dist/*-linux.zip`
  - For Mobile: `dist/*-android.apk`, `dist/*-ios.ipa`
  - For Container: `dist/*-docker.tar.gz`
  - For Package Managers: `dist/*-npm.tgz`, `dist/*-pypi.tar.gz`
- `products/<project>/bom/` - Bill of Materials
  - `bom.json` - List of dependencies
  - `bom.csv` - Spreadsheet format
  - `dependencies.md` - Human-readable format
- `products/<project>/LICENSES.md` - All license texts
- `products/<project>/SECURITY.md` - Security audit results
- `products/<project>/RELEASE.md` - Release notes and instructions

## Tools & Libraries

### Package Building
- **electron-builder** - Electron desktop apps (Win, Mac, Linux)
- **husky** - Git hooks for build validation
- **vsce** - VS Code extensions
- **nx** - Monorepo build tooling
- **create-react-app** - Web app packaging
- **react-native-cli** - Mobile apps

### Security & License
- **trivy** - Vulnerability scanner
- **safety** - Python dependency checker
- **npm audit** - NPM security audit
- **owasp-dep-check** - Dependency check
- **scancode** - License compliance
- **license_finder** - License attribution

### Container & Orchestration
- **dockerfile** - Docker images
- **docker-compose.yml** - Multi-container deployment
- **kubernetes** - K8s manifests
- **helm** - Package manager for K8s

### Windows Specific
- **NSIS** - Installer builder
- **WiX** - XML installer tool
- **Inno Setup** - Installer framework
- **Chocolatey** - Package manager

### macOS Specific
- **pkgbuild** - Package builder
- **productbuild** - Installer
- **homebrew** - Package manager

### Linux Specific
- **snapcraft** - Snap packages
- **flatpak** - Flatpak packages
- **appimage** - AppImage format

### Archive Management
- **zip**, **gzip**, **tar** - Archive utilities
- **7z** - Cross-platform archives

### Distribution
- **npm publish** - NPM packages
- **twine** - PyPI packages
- **aws s3**, **azure storage** - Cloud storage
- **gh release** - GitHub releases

## Workflow

### 1. Dependency Analysis
- Parse `package.json`, `requirements.txt`, `pom.xml`, etc.
- Generate complete dependency tree
- Identify license for each dependency
- Detect security vulnerabilities

### 2. Bill of Materials
- Create `bom.json` with all dependencies
- Generate human-readable `dependencies.md`
- Export CSV for spreadsheet import
- Include license information per dependency

### 3. Security Audit
- Run vulnerability scanners (Trivy, npm audit)
- Check for known security issues
- Generate security report in `SECURITY.md`
- Include remediation recommendations

### 4. License Processing
- Extract all license texts
- Generate `LICENSES.md` with attributions
- Ensure license compliance
- Create license file for redistribution

### 5. Platform-Specific Packaging
Based on `project-config.json` platform:

#### Web Applications
- Build optimized static assets
- Bundle into zip with index.html
- Include service worker if PWA
- Create deployment scripts

#### Desktop Applications (Electron)
- Build for Windows (NSIS installer)
- Build for macOS (DMG/ PKG)
- Build for Linux (AppImage/ deb/ rpm)
- Create universal distribution

#### Mobile Applications
- Build Android APK with signing
- Build iOS IPA with provisioning
- Create cross-platform distribution

#### Container Images
- Create multi-stage Dockerfiles
- Optimize layer size
- Include security scan
- Create docker-compose

#### Package Managers
- Build npm package
- Build PyPI distribution
- Create VS Code extension

### 6. Release Preparation
- Generate `RELEASE.md` with:
  - Version from git tags or config
  - Build timestamp
  - Package checksums
  - Installation instructions
  - Upgrade notes
  - Known issues

### 7. Distribution Setup
- Configure distribution channels
- Set up CDN if needed
- Create update mechanism
- Prepare release assets

### 8. Validation
- Verify all packages install correctly
- Test on target platforms
- Validate licenses
- Check security scan results
- Ensure package integrity

## Configuration
```json
{
  "packaging": {
    "platforms": ["web", "desktop", "mobile", "container"],
    "distDir": "dist",
    "securityScan": true,
    "licenseCheck": true,
    "dockerImage": "productorg/productname:latest",
    "electron": {
      "win": true,
      "mac": true,
      "linux": true,
      "publisherName": "Company"
    },
    "release": {
      "version": "1.0.0",
      "changelog": "CHANGELOG.md",
      "prerelease": false
    }
  }
}
```

## Model Assignment
- **Model Tier**: Uses project's model tier (from project-config.json)
- **Recommended**: Premium tier for quality packages
- **Fallback**: Cheap tier acceptable for basic packages

## Quality Checks
- [ ] All packages install and run
- [ ] Security scan passes (no critical vulnerabilities)
- [ ] Licenses are clearly attributed
- [ ] BOM is complete and accurate
- [ ] All platforms specified are built
- [ ] Package sizes are reasonable
- [ ] Package metadata is correct
- [ ] Distribution ready

## Error Handling
- Build fails → Use cached version or fallback package
- Security scan fails → Mark as warning, continue
- License issues → Skip component, document issue
- Platform not supported → Skip, document requirement
- Package size too large → Optimize, compress, exclude optional features

## Integration Points
- Reads from: `src/`, `docs/`, `reports/`, `project-config.json`, `architecture/`
- Writes to: `dist/`, `bom/`, `LICENSES.md`, `SECURITY.md`, `RELEASE.md`
- Triggers: After Stage 7 (Document) completes successfully
- Depends on: Source code, dependencies, platform specifications