"""Reusable prompt templates for AI workflows."""

from typing import List, Dict, Any

TEMPLATES = {
    "CODEBASE_ANALYSIS": """Analyze the codebase in {directory}:
1. Explore the directory structure and identify main components
2. Understand the purpose and architecture of each component
3. Document key dependencies and relationships
4. Identify patterns, conventions, and standards used

Focus areas: {focus_areas}

Provide a structured analysis with clear sections for:
- Project Overview
- Component Architecture
- Key Files and Their Purposes
- Dependencies and Relationships
- Coding Standards Observed""",

    "FUNCTION_DOCUMENTATION": """Document the following function/method:
File: {file_path}
Function: {function_name}

Generate comprehensive documentation including:
1. Purpose and functionality
2. Parameters with types and descriptions
3. Return value description
4. Usage examples
5. Any side effects or important notes
6. Related functions or methods

Format the documentation according to the project's style.""",

    "TEST_GENERATION": """Generate unit tests for the following code:
File: {file_path}
Target: {target_code}

Requirements:
1. Use the testing framework already in the project: {test_framework}
2. Cover edge cases and error conditions
3. Include both positive and negative test cases
4. Follow the project's test naming conventions
5. Add appropriate assertions and test descriptions

Existing test examples for reference:
{test_examples}""",

    "REFACTORING_PLAN": """Create a refactoring plan for the following code:
Target: {target}
Current issues: {issues}
Desired outcome: {desired_outcome}

Provide a detailed plan including:
1. Analysis of current implementation
2. Proposed changes with rationale
3. Step-by-step refactoring approach
4. Potential risks and mitigation strategies
5. Testing requirements
6. Expected benefits""",

    "CODE_REVIEW": """Review the following code changes:
{diff_content}

Provide a comprehensive review covering:
1. Code quality and readability
2. Potential bugs or issues
3. Performance considerations
4. Security implications
5. Adherence to project standards
6. Suggestions for improvement

Format as actionable feedback with severity levels.""",

    "SECURITY_AUDIT": """Perform a security audit on the following code:
Target: {target}
Context: {context}

Check for:
1. Common vulnerabilities (OWASP Top 10)
2. Input validation issues
3. Authentication/authorization problems
4. Data exposure risks
5. Cryptographic weaknesses
6. Dependency vulnerabilities

Provide findings with:
- Severity level
- Description of issue
- Recommended fix
- Example implementation""",

    "PERFORMANCE_OPTIMIZATION": """Analyze and optimize performance for:
Target: {target}
Current performance metrics: {metrics}
Performance goals: {goals}

Tasks:
1. Identify performance bottlenecks
2. Analyze algorithmic complexity
3. Find inefficient patterns
4. Suggest optimizations
5. Estimate performance improvements

Provide specific, implementable recommendations.""",

    "API_DESIGN": """Design an API for the following requirements:
Purpose: {purpose}
Requirements: {requirements}
Constraints: {constraints}

Deliverables:
1. API endpoint structure
2. Request/response schemas
3. Authentication approach
4. Error handling strategy
5. Rate limiting considerations
6. Example usage code

Follow REST/GraphQL best practices as appropriate.""",

    "DEPENDENCY_ANALYSIS": """Analyze project dependencies:
Project root: {project_root}
Package manager: {package_manager}

Tasks:
1. List all direct and transitive dependencies
2. Identify outdated packages
3. Find security vulnerabilities
4. Detect unused dependencies
5. Analyze license compatibility
6. Suggest dependency updates

Provide actionable recommendations for dependency management.""",

    "MIGRATION_PLAN": """Create a migration plan:
From: {source_version}
To: {target_version}
Scope: {scope}

Include:
1. Breaking changes analysis
2. Step-by-step migration guide
3. Code modification requirements
4. Rollback strategy
5. Testing approach
6. Timeline estimation

Consider backward compatibility and gradual migration options.""",

    "WAKE_SPECIFIC_ANALYSIS": """Analyze Wake-specific code:
Target: {target}
Focus: {focus}

Wake-specific considerations:
1. Analyze test fixtures and their usage
2. Review detector implementations
3. Check LSP integration points
4. Examine CLI command structure
5. Validate configuration handling

Provide Wake-specific recommendations and best practices.""",

    "CUSTOM_WORKFLOW": """Execute custom workflow:
Instructions: {instructions}
Context: {context}
Tools available: {tools}

Follow the provided instructions carefully and provide detailed output."""
}

# Validation functions for templates
def get_template_variables(template_name: str) -> List[str]:
    """Get the required variables for a template."""
    import re
    template = TEMPLATES.get(template_name, "")
    return re.findall(r'\{(\w+)\}', template)

def validate_template_context(template_name: str, context: Dict[str, Any]) -> bool:
    """Validate that all required variables are in context."""
    required_vars = get_template_variables(template_name)
    return all(var in context for var in required_vars)