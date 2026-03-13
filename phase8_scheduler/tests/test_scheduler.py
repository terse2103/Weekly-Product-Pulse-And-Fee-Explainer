import os
import yaml
from pathlib import Path

def test_workflow_file_exists():
    """Ensure the GitHub Actions workflow file exists in the correct directory."""
    workflow_path = Path(".github/workflows/weekly_pulse.yml")
    assert workflow_path.exists(), "Workflow file does not exist at .github/workflows/weekly_pulse.yml"

def test_workflow_yaml_validity():
    """Ensure the workflow YAML is correctly formatted and has the required steps."""
    workflow_path = Path(".github/workflows/weekly_pulse.yml")
    with open(workflow_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    # PyYAML parses unquoted 'on' as boolean True
    on_block = data.get(True, data.get("on", {}))
    
    # Check trigger schedule
    schedule = on_block.get("schedule", [])
    assert len(schedule) > 0, "No schedule defined in workflow"
    assert schedule[0].get("cron") == "0 4 * * 0", "Cron schedule is incorrect, should be '0 4 * * 0'"
    
    # Check workflow_dispatch for manual trigger
    assert "workflow_dispatch" in on_block, "workflow_dispatch is not enabled"


    # Check job and its steps
    assert "run-pulse" in data.get("jobs", {}), "Job 'run-pulse' is missing"
    steps = data["jobs"]["run-pulse"].get("steps", [])
    step_names = [step.get("name") for step in steps]
    
    assert "Checkout repository" in step_names, "Missing 'Checkout repository' step"
    assert "Set up Python" in step_names, "Missing 'Set up Python' step"
    assert "Install dependencies" in step_names, "Missing 'Install dependencies' step"
    assert "Run pipeline" in step_names, "Missing 'Run pipeline' step"
    assert "Upload artifacts" in step_names, "Missing 'Upload artifacts' step"
    assert "Commit outputs to repo" in step_names, "Missing 'Commit outputs to repo' step"

def test_documentation_exists():
    """Ensure the setup documentation for Phase 8 exists."""
    doc_path = Path("phase8_scheduler/docs/scheduler_setup.md")
    assert doc_path.exists(), "Setup documentation is missing"
