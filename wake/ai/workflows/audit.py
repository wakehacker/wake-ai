"""Security audit workflow implementation."""

from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple, Union
import yaml

from wake.ai.claude import ClaudeCodeSession

from ..flow import AIWorkflow, WorkflowStep, ClaudeCodeResponse


class AuditWorkflow(AIWorkflow):
    """Fixed security audit workflow following industry best practices."""

    name = "audit"
    # Default tools for auditing - needs read, write, edit, and bash capabilities
    allowed_tools = ["Read", "Write", "Edit", "Bash", "Grep", "Glob", "LS", "Task", "TodoWrite", "MultiEdit"]

    def __init__(
        self,
        scope_files: Optional[List[str]] = None,
        context_docs: Optional[List[str]] = None,
        focus_areas: Optional[List[str]] = None,
        session: Optional[ClaudeCodeSession] = None,
        model: Optional[str] = None,
        working_dir: Optional[Union[str, Path]] = None,
        execution_dir: Optional[Union[str, Path]] = None,
        **kwargs
    ):
        """Initialize security audit workflow.

        Args:
            scope_files: List of files to audit (None = entire codebase)
            context_docs: Additional documentation/context files
            focus_areas: Specific vulnerabilities or ERCs to focus on
            session: Claude session to use
        """
        self.scope_files = scope_files or []
        self.context_docs = context_docs or []
        self.focus_areas = focus_areas or []

        # Load prompts from markdown files before parent init
        self._load_prompts()

        # Now call parent init which will call _setup_steps
        super().__init__(name=self.name, session=session, model=model, working_dir=working_dir, execution_dir=execution_dir, **kwargs)

        # Add context after parent init (which creates self.state)
        self.add_context("scope_files", self.scope_files)
        self.add_context("context_docs", self.context_docs)
        self.add_context("focus_areas", self.focus_areas)

    def _load_prompts(self):
        """Load audit prompts from markdown files."""
        prompts_dir = Path(__file__).parent.parent / "prompts"

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
            tools=["Read", "Write", "Edit", "Bash", "Grep", "LS"],
            max_cost=5.0,
            validator=self._validate_initialize,
            max_retries=3,
            max_retry_cost=2.0
        )

        # Step 1: Analyze and Plan
        self.add_step(
            name="analyze_and_plan",
            prompt_template=self._build_prompt("analyze_and_plan"),
            tools=["Read", "Write", "Edit", "Bash", "Grep", "LS", "TodoWrite"],
            max_cost=15.0,
            validator=self._validate_analyze_and_plan,
            max_retries=3,
            max_retry_cost=5.0
        )

        # Step 2: Manual Review
        self.add_step(
            name="manual_review",
            prompt_template=self._build_prompt("manual_review"),
            tools=["Read", "Write", "Edit", "Bash", "Grep", "LS"],
            max_cost=20.0,
            validator=self._validate_manual_review,
            max_retries=3,
            max_retry_cost=10.0
        )

        # Step 3: Executive Summary
        self.add_step(
            name="executive_summary",
            prompt_template=self._build_prompt("executive_summary"),
            tools=["Read", "Write", "Edit", "Bash"],
            max_cost=10.0,
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
        overview_file = Path(self.working_dir) / "audit" / "overview.md"
        if not overview_file.exists():
            errors.append(f"Overview file not created at {overview_file}")
        else:
            content = overview_file.read_text()
            required_sections = ["# Codebase Overview", "## Architecture", "## Key Components", "## Actors"]
            for section in required_sections:
                if section not in content:
                    errors.append(f"Missing required section '{section}' in overview.md")

        # Check for plan.yaml
        plan_file = Path(self.working_dir) / "audit" / "plan.yaml"
        if not plan_file.exists():
            errors.append(f"Plan file not created at {plan_file}")
        else:
            try:
                # Load YAML directly
                with open(plan_file, 'r') as f:
                    plan_data = yaml.safe_load(f)

                # Validate YAML schema
                if 'contracts' not in plan_data:
                    errors.append("Missing 'contracts' key in YAML")
                else:
                    for i, contract in enumerate(plan_data['contracts']):
                        if 'name' not in contract:
                            errors.append(f"Contract {i} missing 'name' field")
                        if 'issues' not in contract:
                            errors.append(f"Contract {i} missing 'issues' field")
                        else:
                            for j, issue in enumerate(contract['issues']):
                                required_fields = ['title', 'status', 'location', 'description', 'severity']
                                for field in required_fields:
                                    if field not in issue:
                                        errors.append(f"Contract {contract.get('name', i)} issue {j} missing '{field}' field")

                                # Validate location structure
                                if 'location' in issue:
                                    loc = issue['location']
                                    if 'lines' not in loc and 'function' not in loc:
                                        errors.append(f"Contract {contract.get('name', i)} issue {j} location missing 'lines' or 'function'")

                                # Validate severity values
                                if 'severity' in issue and issue['severity'] not in ['info', 'warning', 'low', 'medium', 'high']:
                                    errors.append(f"Contract {contract.get('name', i)} issue {j} has invalid severity: {issue['severity']}")

                                # Validate status
                                if 'status' in issue and issue['status'] != 'pending':
                                    errors.append(f"Contract {contract.get('name', i)} issue {j} should have status 'pending', not '{issue['status']}'")

            except yaml.YAMLError as e:
                errors.append(f"Invalid YAML in plan.yaml: {str(e)}")
            except Exception as e:
                errors.append(f"Error validating plan.yaml structure: {str(e)}")

        return (len(errors) == 0, errors)

    def _validate_manual_review(self, response: ClaudeCodeResponse) -> Tuple[bool, List[str]]:
        """Validate manual review step - check for updated plan and issue files."""
        errors = []

        # Check that plan.yaml still exists and has been updated
        plan_file = Path(self.working_dir) / "audit" / "plan.yaml"
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
                            errors.append(f"Issue '{issue.get('title')}' missing validation comment")

                if not has_validated_issues:
                    errors.append("No issues have been validated (all still pending)")

                # Check for issue files for true positives
                issues_dir = Path(self.working_dir) / "audit" / "issues"
                if true_positives and not issues_dir.exists():
                    errors.append(f"Issues directory not created at {issues_dir}")
                elif true_positives:
                    # Check that at least some issue files exist
                    adoc_files = list(issues_dir.glob("*.adoc"))
                    if len(adoc_files) == 0:
                        errors.append("No issue files (*.adoc) created for true positive findings")

            except yaml.YAMLError as e:
                errors.append(f"Invalid YAML in updated plan.yaml: {str(e)}")
            except Exception as e:
                errors.append(f"Error validating updated plan.yaml: {str(e)}")

        return (len(errors) == 0, errors)

    def _validate_executive_summary(self, response: ClaudeCodeResponse) -> Tuple[bool, List[str]]:
        """Validate executive summary step."""
        errors = []

        # Check for executive-summary.md
        summary_file = Path(self.working_dir) / "audit" / "executive-summary.md"
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
                    errors.append(f"Missing required section '{section}' in executive-summary.md")

            # Check for findings table
            if "| Severity | Count |" not in content:
                errors.append("Missing severity findings table in executive-summary.md")

            # Check minimum content length
            if len(content) < 500:
                errors.append("Executive summary is too short (minimum 500 characters)")

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

    def execute(self, context: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
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

    @classmethod
    def get_cli_options(cls) -> Dict[str, Any]:
        """Return audit workflow CLI options."""
        import click
        return {
            "scope": {
                "param_decls": ["-s", "--scope"],
                "multiple": True,
                "type": click.Path(exists=True),
                "help": "Files/directories in audit scope (default: entire codebase)"
            },
            "context": {
                "param_decls": ["-c", "--context"],
                "multiple": True,
                "type": click.Path(exists=True),
                "help": "Additional context files (docs, specs, etc.)"
            },
            "focus": {
                "param_decls": ["-f", "--focus"],
                "multiple": True,
                "help": "Focus areas (e.g., 'reentrancy', 'ERC20', 'access-control')"
            }
        }

    @classmethod
    def process_cli_args(cls, **kwargs) -> Dict[str, Any]:
        """Process CLI arguments for audit workflow."""
        return {
            "scope_files": list(kwargs.get("scope", [])),
            "context_docs": list(kwargs.get("context", [])),
            "focus_areas": list(kwargs.get("focus", []))
        }