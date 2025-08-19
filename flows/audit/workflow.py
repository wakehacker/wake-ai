"""Security audit workflow implementation."""

from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
import yaml

import rich_click as click

from wake_ai import workflow
from wake_ai.core.flow import AIWorkflow, ClaudeCodeResponse, AIResult

# Valid detection types for audit findings
VALID_DETECTION_TYPES = [
    "Data validation", "Code quality", "Logic error", "Standards violation",
    "Gas optimization", "Logging", "Trust model", "Arithmetics",
    "Access control", "Unused code", "Storage clashes", "Denial of service",
    "Front-running", "Replay attack", "Reentrancy", "Function visibility",
    "Overflow/Underflow", "Configuration", "Reinitialization", "Griefing", "N/A"
]


@workflow.command(name="audit")
@click.option("--scope", "-s", type=click.Path(exists=True), multiple=True, help="Files/directories in audit scope (default: entire codebase)")
@click.option("--context", "-c", type=click.Path(exists=True), multiple=True, help="Additional context files (docs, specs, etc.)")
@click.option("--focus", "-f", type=str, multiple=True, help="Focus areas (e.g., 'reentrancy', 'ERC20', 'access-control')")
def factory(scope: List[str], context: List[str], focus: List[str]):
    """Run audit workflow."""
    workflow = AuditWorkflow()
    workflow.scope_files = scope
    workflow.context_docs = context
    workflow.focus_areas = focus

    # Add context after parent init (which creates self.state)
    workflow.add_context("scope_files", workflow.scope_files)
    workflow.add_context("context_docs", workflow.context_docs)
    workflow.add_context("focus_areas", workflow.focus_areas)

    return workflow


class AuditWorkflow(AIWorkflow):
    """Fixed security audit workflow following industry best practices."""

    scope_files: List[str]
    context_docs: List[str]
    focus_areas: List[str]

    # Preserve audit results by default
    cleanup_working_dir = False

    def __init__(self):
        """Initialize security audit workflow."""
        super().__init__()

        # Load prompts from markdown files before parent init
        self._load_prompts()

        # Import result class
        from .result import AuditResult

        self.result_class = AuditResult

    def _load_prompts(self):
        """Load audit prompts from markdown files."""
        prompts_dir = Path(__file__).parent / "prompts"

        self.prompts = {}
        # Updated prompt files matching new structure
        prompt_files = [
            ("initialize", "0-initialize.md"),
            ("analyze_and_plan", "1-analyze-and-plan.md"),
            ("manual_review", "2-manual-review.md"),
            ("executive_summary", "3-executive-summary.md")
        ]

        for key, filename in prompt_files:
            prompt_path = prompts_dir / filename
            if prompt_path.exists():
                self.prompts[key] = prompt_path.read_text()
            else:
                raise FileNotFoundError(f"Audit prompt not found: {prompt_path}")

    def _setup_steps(self):
        """Setup the fixed audit workflow steps."""

        # Step 0: Initialize
        self.add_step(
            name="initialize",
            prompt_template=self._build_prompt("initialize"),
            allowed_tools=None,  # Use secure defaults from parent class
            max_cost=5.0,
            validator=self._validate_initialize,
            max_retries=3,
            max_retry_cost=2.0
        )

        # Step 1: Analyze and Plan
        self.add_step(
            name="analyze_and_plan",
            prompt_template=self._build_prompt("analyze_and_plan"),
            allowed_tools=None,  # Use secure defaults from parent class (includes TodoWrite)
            max_cost=10.0,
            validator=self._validate_analyze_and_plan,
            max_retries=3,
            max_retry_cost=5.0
        )

        # Step 2: Manual Review
        self.add_step(
            name="manual_review",
            prompt_template=self._build_prompt("manual_review"),
            allowed_tools=None,  # Use secure defaults from parent class
            max_cost=10.0,
            validator=self._validate_manual_review,
            max_retries=3,
            max_retry_cost=10.0
        )

        # Step 3: Executive Summary
        self.add_step(
            name="executive_summary",
            prompt_template=self._build_prompt("executive_summary"),
            allowed_tools=None,  # Use secure defaults from parent class
            max_cost=5.0,
            validator=self._validate_executive_summary,
            max_retries=2,
            max_retry_cost=5.0
        )

    def _validate_initialize(self, response: ClaudeCodeResponse) -> Tuple[bool, List[str]]:
        """Validate initialization step - check if wake init was successful."""
        errors = []

        # Check if wake.toml exists (created by wake init)
        wake_config = Path(self.execution_dir) / "wake.toml"
        if not wake_config.exists():
            # Check in parent directory too as wake might be initialized there
            parent_wake_config = Path(self.execution_dir).parent / "wake.toml"
            if not parent_wake_config.exists():
                errors.append("wake.toml not found - wake init may have failed")

        return (len(errors) == 0, errors)

    def _validate_analyze_and_plan(self, response: ClaudeCodeResponse) -> Tuple[bool, List[str]]:
        """Validate analyze and plan step - check for required files and YAML structure."""
        errors = []

        # Check for overview.md
        overview_file = Path(self.working_dir) / "overview.md"
        if not overview_file.exists():
            errors.append(f"Overview file not created at {overview_file}")
        else:
            content = overview_file.read_text()
            required_sections = ["# Codebase Overview", "## Architecture", "## Key Components", "## Actors"]
            for section in required_sections:
                if section not in content:
                    errors.append(f"Missing required section '{section}' in {overview_file}")

        # Check for plan.yaml
        plan_file = Path(self.working_dir) / "plan.yaml"
        if not plan_file.exists():
            errors.append(f"Plan file not created at {plan_file}")
        else:
            try:
                # Load YAML directly
                with open(plan_file, 'r') as f:
                    plan_data = yaml.safe_load(f)

                # Validate YAML schema
                if 'contracts' not in plan_data:
                    errors.append(f"Missing 'contracts' key in {plan_file}")
                else:
                    for i, contract in enumerate(plan_data['contracts']):
                        if 'name' not in contract:
                            errors.append(f"Contract {i} missing 'name' field")
                        if 'issues' not in contract:
                            errors.append(f"Contract {i} missing 'issues' field")
                        else:
                            for j, issue in enumerate(contract['issues']):
                                required_fields = ['title', 'status', 'location', 'description', 'impact', 'confidence']
                                for field in required_fields:
                                    if field not in issue:
                                        errors.append(f"Contract {contract.get('name', i)} issue {j} missing '{field}' field")

                                # Validate location structure
                                if 'location' in issue:
                                    loc = issue['location']
                                    if 'lines' not in loc and 'function' not in loc:
                                        errors.append(f"Contract {contract.get('name', i)} issue {j} location missing 'lines' or 'function'")

                                # Validate impact values
                                if 'impact' in issue and issue['impact'] not in ['high', 'medium', 'low', 'info', 'warning']:
                                    errors.append(f"Contract {contract.get('name', i)} issue {j} has invalid impact: {issue['impact']}")

                                # Validate confidence values
                                if 'confidence' in issue and issue['confidence'] not in ['high', 'medium', 'low']:
                                    errors.append(f"Contract {contract.get('name', i)} issue {j} has invalid confidence: {issue['confidence']}")

                                # Validate status
                                if 'status' in issue and issue['status'] != 'pending':
                                    errors.append(f"Contract {contract.get('name', i)} issue {j} should have status 'pending', not '{issue['status']}'")

            except yaml.YAMLError as e:
                errors.append(f"Invalid YAML in {plan_file}: {str(e)}")
            except Exception as e:
                errors.append(f"Error validating {plan_file} structure: {str(e)}")

        return (len(errors) == 0, errors)

    def _validate_manual_review(self, response: ClaudeCodeResponse) -> Tuple[bool, List[str]]:
        """Validate manual review step - check for updated plan and issue files."""
        errors = []

        # Check that plan.yaml still exists and has been updated
        plan_file = Path(self.working_dir) / "plan.yaml"
        if not plan_file.exists():
            errors.append(f"Plan file missing at {plan_file}")
        else:
            try:
                # Load YAML directly
                with open(plan_file, 'r') as f:
                    plan_data = yaml.safe_load(f)

                # Check that statuses have been updated from 'pending'
                has_validated_issues = False
                true_positives = []

                for contract in plan_data.get('contracts', []):
                    for issue in contract.get('issues', []):
                        status = issue.get('status', '')
                        if status in ['true_positive', 'false_positive']:
                            has_validated_issues = True
                            if status == 'true_positive':
                                true_positives.append((contract.get('name'), issue))

                        # Check for comment field when validated
                        if status != 'pending' and 'comment' not in issue:
                            errors.append(f"Issue '{issue.get('title')}' in {plan_file} missing validation comment")

                if not has_validated_issues:
                    errors.append(f"No issues have been validated in {plan_file} (all still pending)")

                # Check for issue files for true positives
                issues_dir = Path(self.working_dir) / "issues"
                if true_positives and not issues_dir.exists():
                    errors.append(f"Issues directory not created at {issues_dir}")
                elif true_positives:
                    # Check that at least some issue files exist
                    yaml_files = list(issues_dir.glob("*.yaml"))
                    if len(yaml_files) == 0:
                        errors.append(f"No issue files (*.yaml) created for true positive findings in {issues_dir}")
                    else:
                        # Validate YAML file structure
                        for yaml_file in yaml_files[:3]:  # Check first 3 files as samples
                            try:
                                with open(yaml_file, 'r') as f:
                                    issue_data = yaml.safe_load(f)

                                if not isinstance(issue_data, dict):
                                    errors.append(f"Issue file {yaml_file.name} is not a valid YAML dictionary")
                                    continue

                                # Check for required fields
                                required_fields = ['name', 'impact', 'confidence', 'detection_type', 'location', 'description', 'recommendation']
                                missing_fields = [field for field in required_fields if field not in issue_data]
                                if missing_fields:
                                    errors.append(f"Issue file {yaml_file.name} missing fields: {', '.join(missing_fields)}")

                                # Validate detection_type
                                if 'detection_type' in issue_data:
                                    detection_type = issue_data['detection_type']
                                    if detection_type not in VALID_DETECTION_TYPES:
                                        errors.append(f"Issue file {yaml_file.name} has invalid detection_type '{detection_type}'. Valid types are: {', '.join(VALID_DETECTION_TYPES)}")

                                # Validate location structure
                                if 'location' in issue_data and isinstance(issue_data['location'], dict):
                                    loc = issue_data['location']
                                    loc_required = ['file', 'start_line', 'end_line']
                                    loc_missing = [field for field in loc_required if field not in loc]
                                    if loc_missing:
                                        errors.append(f"Issue file {yaml_file.name} location missing: {', '.join(loc_missing)}")

                            except yaml.YAMLError as e:
                                errors.append(f"Issue file {yaml_file.name} has invalid YAML: {str(e)}")
                            except Exception as e:
                                errors.append(f"Error reading issue file {yaml_file.name}: {str(e)}")

            except yaml.YAMLError as e:
                errors.append(f"Invalid YAML in updated {plan_file}: {str(e)}")
            except Exception as e:
                errors.append(f"Error validating updated {plan_file}: {str(e)}")

        return (len(errors) == 0, errors)

    def _validate_executive_summary(self, response: ClaudeCodeResponse) -> Tuple[bool, List[str]]:
        """Validate executive summary step."""
        errors = []

        # Check for executive-summary.md
        summary_file = Path(self.working_dir) / "executive-summary.md"
        if not summary_file.exists():
            errors.append(f"Executive summary not created at {summary_file}")
        else:
            content = summary_file.read_text()
            required_sections = [
                "# Executive Summary",
                "## Audit Overview",
                "## Summary of Findings",
                "## Key Technical Findings"
            ]

            for section in required_sections:
                if section not in content:
                    errors.append(f"Missing required section '{section}' in {summary_file}")

            # Check for the EXACT table format from the prompt
            table_headers = ["| Impact", "| High Confidence", "| Medium Confidence", "| Low Confidence", "| Total"]
            if not all(header in content for header in table_headers):
                errors.append(
                    f"Missing findings summary table in {summary_file}. The executive summary must include a table with "
                    "this exact header row: | Impact | High Confidence | Medium Confidence | Low Confidence | Total |"
                )

            # Also check for table separator line
            if "| Impact" in content and not any("|---" in line for line in content.split('\n') if "---" in line):
                errors.append(
                    f"Findings table missing separator line in {summary_file}. Tables must have a separator line "
                    "like |----------|----------------|-------------------|----------------|-------|"
                )

            # Check minimum content length
            if len(content) < 500:
                errors.append(f"Executive summary in {summary_file} is too short (minimum 500 characters)")

        return (len(errors) == 0, errors)

    def _build_prompt(self, step_name: str) -> str:
        """Build prompt with context variables."""
        base_prompt = self.prompts[step_name]

        # Add context variables to the prompt
        context_section = ""
        if step_name in ["analyze_and_plan", "executive_summary"]:
            context_section = f"\n<context>\nScope: {', '.join(self.scope_files) if self.scope_files else 'entire codebase'}\n"
            context_section += f"Context: {', '.join(self.context_docs) if self.context_docs else 'none'}\n"
            context_section += f"Focus: {', '.join(self.focus_areas) if self.focus_areas else 'general security audit'}\n</context>\n"

        # Replace context placeholders if they exist
        if "{scope_files}" in base_prompt:
            base_prompt = base_prompt.replace("{scope_files}", ', '.join(self.scope_files) if self.scope_files else 'entire codebase')
        if "{context_docs}" in base_prompt:
            base_prompt = base_prompt.replace("{context_docs}", ', '.join(self.context_docs) if self.context_docs else 'none')
        if "{focus_areas}" in base_prompt:
            base_prompt = base_prompt.replace("{focus_areas}", ', '.join(self.focus_areas) if self.focus_areas else 'general security audit')

        return base_prompt

    def execute(self, context: Optional[Dict[str, Any]] = None, **kwargs) -> Tuple[Dict[str, Any], AIResult]:
        """Execute the audit workflow with proper context setup."""
        # Initialize context with audit-specific information
        audit_context = {
            "scope": ', '.join(self.scope_files) if self.scope_files else 'entire codebase',
            "additional_context": ', '.join(self.context_docs) if self.context_docs else 'none',
            "focus_areas": ', '.join(self.focus_areas) if self.focus_areas else "general security audit"
        }

        if context:
            audit_context.update(context)

        # Execute the workflow
        results = super().execute(context=audit_context, **kwargs)

        return results
