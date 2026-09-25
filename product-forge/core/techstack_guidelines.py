"""
Dynamic Techstack Guidelines Generator

Generates coding guidelines for ANY techstack dynamically.
If guidelines are missing for a techstack, generates them from:
- Industry best practices
- Official documentation patterns
- Common conventions

Supports: Flutter, .NET, Java, Ruby, Rust, PHP, and more.
"""
import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime


@dataclass
class TechStackGuidelines:
    """Generated guidelines for a techstack."""
    techstack: str
    language: str
    framework: str
    guidelines_file: str
    generated_at: str
    sections: List[Dict[str, str]] = field(default_factory=list)
    coding_standards: List[str] = field(default_factory=list)
    best_practices: List[str] = field(default_factory=list)
    anti_patterns: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def to_markdown(self) -> str:
        """Convert to markdown format."""
        lines = [
            f"# {self.techstack} Coding Guidelines",
            "",
            f"> Auto-generated guidelines for {self.language}/{self.framework}",
            f"> Generated: {self.generated_at}",
            "",
            "## Coding Standards",
            "",
        ]
        for standard in self.coding_standards:
            lines.append(f"- {standard}")
        
        lines.extend(["", "## Best Practices", ""])
        for practice in self.best_practices:
            lines.append(f"- {practice}")
        
        lines.extend(["", "## Anti-Patterns to Avoid", ""])
        for anti_pattern in self.anti_patterns:
            lines.append(f"- {anti_pattern}")
        
        return "\n".join(lines)


# Pre-defined techstack guidelines
TECHSTACK_DEFINITIONS = {
    "flutter": TechStackGuidelines(
        techstack="flutter",
        language="dart",
        framework="flutter",
        guidelines_file="docs/guidelines/coding/flutter/style-guide.md",
        generated_at=datetime.now().isoformat(),
        coding_standards=[
            "Use meaningful variable and function names",
            "Follow Dart naming conventions (lowerCamelCase for variables, UpperCamelCase for classes)",
            "Keep widgets small and focused on single responsibility",
            "Use const constructors where possible",
            "Prefer StatelessWidget over StatefulWidget when no state management needed",
            "Use proper widget composition over inheritance",
            "Handle errors with try-catch and provide user-friendly messages",
            "Use async/await for asynchronous operations",
            "Follow Flutter's file structure convention (lib/, test/, assets/)",
            "Use meaningful widget names that describe their purpose",
        ],
        best_practices=[
            "Separate business logic from UI (use BLoC, Provider, or Riverpod)",
            "Keep widget tree shallow to avoid performance issues",
            "Use const widgets to reduce rebuilds",
            "Implement proper state management",
            "Use keys for widgets that can be reordered",
            "Optimize images and assets for mobile",
            "Implement proper navigation with named routes",
            "Use theme data for consistent styling",
            "Write unit and widget tests",
            "Use lint rules (flutter_lints, very_good_analysis)",
        ],
        anti_patterns=[
            "Don't put business logic in widgets",
            "Don't use setState for complex state management",
            "Don't ignore lint warnings",
            "Don't hardcode strings (use localization)",
            "Don't use magic numbers (define constants)",
            "Don't create deep widget nesting",
            "Don't forget to dispose controllers and subscriptions",
            "Don't use print() for debugging (use logging package)",
        ],
    ),
    "dotnet": TechStackGuidelines(
        techstack="dotnet",
        language="csharp",
        framework=".net",
        guidelines_file="docs/guidelines/coding/dotnet/style-guide.md",
        generated_at=datetime.now().isoformat(),
        coding_standards=[
            "Use PascalCase for public members and types",
            "Use camelCase for private fields and local variables",
            "Prefix private fields with underscore (_fieldName)",
            "Use interfaces with I prefix (IRepository, IService)",
            "Use async/await for asynchronous operations",
            "Implement IDisposable for unmanaged resources",
            "Use regions to organize code logically",
            "Follow .NET naming guidelines",
            "Use var when type is obvious",
            "Prefer explicit types when not obvious",
        ],
        best_practices=[
            "Use dependency injection for loose coupling",
            "Implement repository pattern for data access",
            "Use CQRS for complex business logic",
            "Implement proper error handling with middleware",
            "Use logging framework (Serilog, NLog)",
            "Implement health checks for APIs",
            "Use AutoMapper for object mapping",
            "Implement FluentValidation for input validation",
            "Use xUnit or NUnit for testing",
            "Follow SOLID principles",
        ],
        anti_patterns=[
            "Don't use static classes for business logic",
            "Don't ignore compiler warnings",
            "Don't use Task.Result (deadlock risk)",
            "Don't forget to await async calls",
            "Don't use string concatenation (use interpolation)",
            "Don't catch generic exceptions",
            "Don't use lock() with async code",
            "Don't dispose objects prematurely",
        ],
    ),
    "java": TechStackGuidelines(
        techstack="java",
        language="java",
        framework="spring",
        guidelines_file="docs/guidelines/coding/java/style-guide.md",
        generated_at=datetime.now().isoformat(),
        coding_standards=[
            "Use camelCase for methods and variables",
            "Use PascalCase for class names",
            "Use UPPER_SNAKE_CASE for constants",
            "Follow Java naming conventions",
            "Use meaningful variable names",
            "Keep methods short and focused",
            "Use proper indentation (4 spaces)",
            "Add Javadoc for public methods",
            "Use @Override annotation when overriding",
            "Use final for immutable fields",
        ],
        best_practices=[
            "Use Spring Boot for rapid development",
            "Implement RESTful APIs with proper HTTP methods",
            "Use dependency injection (Spring IoC)",
            "Implement repository pattern with JPA",
            "Use DTOs for data transfer",
            "Implement proper exception handling",
            "Use Lombok to reduce boilerplate",
            "Write unit tests with JUnit 5",
            "Use Maven or Gradle for build management",
            "Follow SOLID principles",
        ],
        anti_patterns=[
            "Don't use System.out.println for logging",
            "Don't catch generic Exception",
            "Don't use raw types (use generics)",
            "Don't create circular dependencies",
            "Don't ignore null pointer exceptions",
            "Don't use string concatenation in loops",
            "Don't forget to close resources (use try-with-resources)",
            "Don't use == for string comparison",
        ],
    ),
    "ruby": TechStackGuidelines(
        techstack="ruby",
        language="ruby",
        framework="rails",
        guidelines_file="docs/guidelines/coding/ruby/style-guide.md",
        generated_at=datetime.now().isoformat(),
        coding_standards=[
            "Use snake_case for methods and variables",
            "Use CamelCase for class names",
            "Use SCREAMING_SNAKE_CASE for constants",
            "Follow Ruby naming conventions",
            "Use 2 spaces for indentation",
            "Keep lines under 80 characters",
            "Use meaningful variable names",
            "Add comments for complex logic",
            "Use Ruby-style string interpolation",
            "Prefer single quotes unless string interpolation needed",
        ],
        best_practices=[
            "Use Rails conventions (MVC, RESTful routes)",
            "Implement fat models, skinny controllers",
            "Use ActiveRecord validations",
            "Implement proper error handling",
            "Use Rails migrations for database changes",
            "Write RSpec tests",
            "Use Gems for common functionality",
            "Implement proper authentication (Devise)",
            "Use Rails caching strategies",
            "Follow DRY principle",
        ],
        anti_patterns=[
            "Don't put business logic in controllers",
            "Don't ignore Rails security best practices",
            "Don't use eval() or instance_eval() unsafely",
            "Don't forget to sanitize user input",
            "Don't use select_all (use find_each for large datasets)",
            "Don't ignore N+1 query warnings",
            "Don't hardcode secrets (use credentials)",
        ],
    ),
    "rust": TechStackGuidelines(
        techstack="rust",
        language="rust",
        framework="actix",
        guidelines_file="docs/guidelines/coding/rust/style-guide.md",
        generated_at=datetime.now().isoformat(),
        coding_standards=[
            "Use snake_case for functions and variables",
            "Use PascalCase for types and traits",
            "Use SCREAMING_SNAKE_CASE for constants",
            "Follow Rust naming conventions",
            "Use 4 spaces for indentation",
            "Add documentation comments (///)",
            "Use meaningful variable names",
            "Prefer immutable by default",
            "Use proper error handling with Result",
        ],
        best_practices=[
            "Use Cargo for dependency management",
            "Implement proper error handling with thiserror/anyhow",
            "Use traits for abstraction",
            "Implement proper testing with #[test]",
            "Use clippy for linting",
            "Use rustfmt for formatting",
            "Implement proper logging with log crate",
            "Use async/await for async operations",
            "Implement proper serialization with serde",
        ],
        anti_patterns=[
            "Don't use unwrap() in production code",
            "Don't ignore compiler warnings",
            "Don't use unsafe unless absolutely necessary",
            "Don't create circular references",
            "Don't forget to handle errors",
            "Don't use println! for debugging (use log)",
        ],
    ),
    "php": TechStackGuidelines(
        techstack="php",
        language="php",
        framework="laravel",
        guidelines_file="docs/guidelines/coding/php/style-guide.md",
        generated_at=datetime.now().isoformat(),
        coding_standards=[
            "Use PascalCase for class names",
            "Use camelCase for methods and variables",
            "Use UPPER_SNAKE_CASE for constants",
            "Follow PSR-12 coding style",
            "Use strict types declaration",
            "Add type hints for parameters and return types",
            "Use meaningful variable names",
            "Keep methods short and focused",
        ],
        best_practices=[
            "Use Laravel conventions (MVC, Eloquent)",
            "Implement proper authentication (Laravel Sanctum)",
            "Use Eloquent ORM for database operations",
            "Implement proper validation with Form Requests",
            "Use Laravel queues for background jobs",
            "Write PHPUnit tests",
            "Use Laravel's built-in caching",
            "Implement proper API resources",
        ],
        anti_patterns=[
            "Don't put business logic in controllers",
            "Don't use raw SQL without parameter binding",
            "Don't ignore SQL injection risks",
            "Don't hardcode credentials",
            "Don't use eval() or dynamic code execution",
            "Don't forget to sanitize user input",
        ],
    ),
}


class TechStackGuidelinesGenerator:
    """Generate guidelines for any techstack."""
    
    def __init__(self, guidelines_dir: str = "docs/guidelines"):
        self.guidelines_dir = Path(guidelines_dir)
    
    def get_guidelines(self, techstack: str) -> Optional[TechStackGuidelines]:
        """Get guidelines for a techstack, generating if needed."""
        techstack_lower = techstack.lower()
        
        # Check if pre-defined guidelines exist
        if techstack_lower in TECHSTACK_DEFINITIONS:
            return TECHSTACK_DEFINITIONS[techstack_lower]
        
        # Check if guidelines file exists
        guidelines_file = self.guidelines_dir / "coding" / techstack_lower / "style-guide.md"
        if guidelines_file.exists():
            return self._load_from_file(guidelines_file, techstack_lower)
        
        # Generate guidelines dynamically
        return self._generate_guidelines(techstack_lower)
    
    def _load_from_file(self, file_path: Path, techstack: str) -> TechStackGuidelines:
        """Load guidelines from existing file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse markdown into sections
            sections = []
            current_section = None
            for line in content.split('\n'):
                if line.startswith('## '):
                    if current_section:
                        sections.append(current_section)
                    current_section = {"title": line[3:].strip(), "content": ""}
                elif current_section:
                    current_section["content"] += line + "\n"
            if current_section:
                sections.append(current_section)
            
            return TechStackGuidelines(
                techstack=techstack,
                language=techstack,
                framework=techstack,
                guidelines_file=str(file_path),
                generated_at=os.path.getmtime(file_path),
                sections=sections,
            )
        except Exception:
            return self._generate_guidelines(techstack)
    
    def _generate_guidelines(self, techstack: str) -> TechStackGuidelines:
        """Generate guidelines for unknown techstack."""
        # Generic guidelines that apply to most techstacks
        return TechStackGuidelines(
            techstack=techstack,
            language=techstack,
            framework=techstack,
            guidelines_file=f"docs/guidelines/coding/{techstack}/style-guide.md",
            generated_at=datetime.now().isoformat(),
            coding_standards=[
                "Use meaningful variable and function names",
                "Follow language-specific naming conventions",
                "Keep functions short and focused",
                "Add comments for complex logic",
                "Use proper indentation",
                "Handle errors gracefully",
                "Write clean, readable code",
            ],
            best_practices=[
                "Follow SOLID principles",
                "Implement proper error handling",
                "Write unit tests",
                "Use version control (Git)",
                "Document public APIs",
                "Use linting tools",
                "Follow DRY principle",
            ],
            anti_patterns=[
                "Don't hardcode values",
                "Don't ignore errors",
                "Don't use magic numbers",
                "Don't create god classes/functions",
                "Don't ignore security best practices",
            ],
        )
    
    def ensure_guidelines_exist(self, techstack: str) -> str:
        """Ensure guidelines exist for techstack, generating if needed."""
        techstack_lower = techstack.lower()
        guidelines_file = self.guidelines_dir / "coding" / techstack_lower / "style-guide.md"
        
        if not guidelines_file.exists():
            guidelines = self.get_guidelines(techstack_lower)
            if guidelines:
                # Create directory
                guidelines_file.parent.mkdir(parents=True, exist_ok=True)
                # Write guidelines
                with open(guidelines_file, 'w', encoding='utf-8') as f:
                    f.write(guidelines.to_markdown())
                return str(guidelines_file)
        
        return str(guidelines_file)
    
    def list_supported_techstacks(self) -> List[str]:
        """List all supported techstacks."""
        supported = list(TECHSTACK_DEFINITIONS.keys())
        
        # Add techstacks with existing guidelines
        coding_dir = self.guidelines_dir / "coding"
        if coding_dir.exists():
            for item in coding_dir.iterdir():
                if item.is_dir() and item.name not in supported:
                    supported.append(item.name)
        
        return sorted(supported)
