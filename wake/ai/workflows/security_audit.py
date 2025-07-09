"""Security audit workflow implementation."""

from pathlib import Path
from typing import List, Optional, Dict, Any

from ..flow import AIWorkflow, WorkflowStep, ClaudeCodeResponse


class SecurityAuditWorkflow(AIWorkflow):
    """Fixed security audit workflow following industry best practices."""
    
    def __init__(
        self,
        scope_files: Optional[List[str]] = None,
        context_docs: Optional[List[str]] = None,
        focus_areas: Optional[List[str]] = None,
        session=None
    ):
        """Initialize security audit workflow.
        
        Args:
            scope_files: List of files to audit (None = entire codebase)
            context_docs: Additional documentation/context files
            focus_areas: Specific vulnerabilities or ERCs to focus on
            session: Claude session to use
        """
        super().__init__("security_audit", session=session)
        self.scope_files = scope_files or []
        self.context_docs = context_docs or []
        self.focus_areas = focus_areas or []
        
        # Load prompts from markdown files
        self._load_prompts()
    
    def _load_prompts(self):
        """Load audit prompts from markdown files."""
        prompts_dir = Path(__file__).parent.parent / "commands"
        
        self.prompts = {}
        # Using the modular approach (1-4 steps)
        prompt_files = [
            ("analyze_and_plan", "1-analyze-and-plan.md"),
            ("static_analysis", "2-static-analysis.md"),
            ("manual_review", "3-manual-review.md"),
            ("executive_summary", "4-executive-summary.md")
        ]
        
        for key, filename in prompt_files:
            prompt_path = prompts_dir / filename
            if prompt_path.exists():
                self.prompts[key] = prompt_path.read_text()
            else:
                raise FileNotFoundError(f"Audit prompt not found: {prompt_path}")
    
    def _setup_steps(self):
        """Setup the fixed audit workflow steps."""
        
        # Step 1: Analyze and Plan
        self.add_step(
            name="analyze_and_plan",
            prompt_template=self._build_prompt("analyze_and_plan"),
            tools=["read", "search", "write", "grep", "bash"],
            context_keys=["scope_context", "additional_context"]
        )
        
        # Step 2: Static Analysis
        self.add_step(
            name="static_analysis",
            prompt_template=self._build_prompt("static_analysis"),
            tools=["read", "write", "bash", "edit"],
            context_keys=["analyze_and_plan_output"]
        )
        
        # Step 3: Manual Review
        self.add_step(
            name="manual_review",
            prompt_template=self._build_prompt("manual_review"),
            tools=["read", "write", "search", "grep", "edit"],
            context_keys=["static_analysis_output", "analyze_and_plan_output"]
        )
        
        # Step 4: Executive Summary
        self.add_step(
            name="executive_summary",
            prompt_template=self._build_prompt("executive_summary"),
            tools=["read", "write"],
            context_keys=["manual_review_output", "analyze_and_plan_output"]
        )
    
    def _build_prompt(self, step_name: str) -> str:
        """Build prompt with context injection points."""
        base_prompt = self.prompts[step_name]
        
        # Add scope information
        if self.scope_files:
            scope_section = f"\n\nFILES IN SCOPE:\n" + "\n".join(f"- {f}" for f in self.scope_files)
        else:
            scope_section = "\n\nSCOPE: Entire codebase"
        
        # Add context documents
        if self.context_docs:
            context_section = f"\n\nADDITIONAL CONTEXT:\n" + "\n".join(f"- {doc}" for doc in self.context_docs)
        else:
            context_section = ""
        
        # Add focus areas
        if self.focus_areas:
            focus_section = f"\n\nFOCUS AREAS:\n" + "\n".join(f"- {area}" for area in self.focus_areas)
        else:
            focus_section = ""
        
        # For steps that need previous outputs, add placeholders
        if step_name != "analyze_and_plan":
            base_prompt = base_prompt + "\n\nPREVIOUS STEP OUTPUTS:\n{previous_outputs}"
        
        return base_prompt + scope_section + context_section + focus_section
    
    def _custom_context_update(self, step_name: str, response: ClaudeCodeResponse):
        """Update context with audit-specific information."""
        # Extract key information from each step
        if step_name == "analyze_and_plan":
            # Parse out the vulnerability checklist for next steps
            self.state.context["vulnerability_checklist"] = self._extract_checklist(response.content)
        elif step_name == "static_analysis":
            # Track which issues were found by static analysis
            self.state.context["static_findings"] = self._extract_static_findings(response.content)
        elif step_name == "manual_review":
            # Track confirmed vulnerabilities
            self.state.context["confirmed_issues"] = self._extract_confirmed_issues(response.content)
    
    def _extract_checklist(self, content: str) -> List[str]:
        """Extract vulnerability checklist from analysis output."""
        # Simple extraction - could be made more sophisticated
        lines = content.split('\n')
        checklist = []
        in_checklist = False
        
        for line in lines:
            if "VULNERABILITY CHECKLIST" in line.upper():
                in_checklist = True
            elif in_checklist and line.strip().startswith('- [ ]'):
                checklist.append(line.strip())
        
        return checklist
    
    def _extract_static_findings(self, content: str) -> Dict[str, Any]:
        """Extract static analysis findings."""
        # Parse wake detect output
        return {"raw_content": content}  # Simplified for now
    
    def _extract_confirmed_issues(self, content: str) -> List[Dict[str, Any]]:
        """Extract confirmed vulnerabilities from manual review."""
        # Parse issue files created
        return []  # Simplified for now
    
    def execute(self, context: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """Execute the audit workflow with proper context setup."""
        # Initialize context with audit-specific information
        audit_context = {
            "scope_context": f"Files in scope: {', '.join(self.scope_files) if self.scope_files else 'entire codebase'}",
            "additional_context": f"Context docs: {', '.join(self.context_docs) if self.context_docs else 'none'}",
            "focus_areas": ", ".join(self.focus_areas) if self.focus_areas else "general security audit"
        }
        
        if context:
            audit_context.update(context)
        
        # Execute the workflow
        results = super().execute(context=audit_context, **kwargs)
        
        # Add audit-specific results
        results["audit_report_path"] = "audit/"
        results["issues_found"] = len(self.state.context.get("confirmed_issues", []))
        
        return results