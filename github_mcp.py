#!/usr/bin/env python3
"""
GitHub MCP Server - A Model Context Protocol server for GitHub repository management.

This server provides tools to:
- Set project names
- Create GitHub repositories
- Clone repositories
- Merge repository contents
- Create files
- Push code changes
- Check file contents

Uses FastMCP framework with stdio transport.
"""

import os
import subprocess
import shutil
import stat
import tempfile
import logging
from pathlib import Path
from typing import Optional
from github import Github
from dotenv import load_dotenv
from fastmcp import FastMCP

# Load environment variables
load_dotenv()

# --- Configuration & Constants ---

# Initialize FastMCP server
mcp = FastMCP("github-mcp")

# GitHub Configuration
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
REPO2_URL = "https://github.com/Jeetanshu18/react-vite"

# Global context storage
context = {}

if not GITHUB_TOKEN:
    logging.warning("GITHUB_TOKEN environment variable not set.")

# Initialize GitHub client
github_client = None
github_user = None

if GITHUB_TOKEN:
    try:
        github_client = Github(GITHUB_TOKEN)
        github_user = github_client.get_user()
        logging.info("GitHub client initialized successfully")
    except Exception as e:
        logging.error(f"Failed to initialize GitHub client: {str(e)}")
        github_client = None
        github_user = None

def _run_git_command(command: list, cwd: Path) -> tuple[bool, str]:
    """Run a git command and return success status and output."""
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, f"Git command failed: {e.stderr}"
    except Exception as e:
        return False, f"Error running git command: {str(e)}"

def _remove_readonly(func, path, exc_info):
    """Remove read-only attribute and retry deletion (Windows compatibility)."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass  # If we can't remove it, continue anyway

def _safe_rmtree(path: Path) -> bool:
    """Safely remove directory tree, handling Windows read-only files."""
    try:
        if path.exists():
            # Use shutil.rmtree with error handler for Windows compatibility
            # Try modern onexc first, fallback to onerror for older Python versions
            try:
                shutil.rmtree(path, onexc=_remove_readonly)
            except TypeError:
                # Fallback for Python < 3.12
                shutil.rmtree(path, onerror=_remove_readonly)
        return True
    except Exception as e:
        logging.warning(f"Could not fully remove directory {path}: {e}")
        return False

@mcp.tool
def set_project_name(name: str) -> str:
    """Set a project name for use in subsequent repository operations."""
    if not GITHUB_TOKEN:
        return "GITHUB_TOKEN is missing. Cannot process any requests."

    context['project_name'] = name
    return f"Project name set to {name}"

@mcp.tool
def setup_existing_repository(repo_name: str) -> str:
    """Set up context for working with an existing repository."""
    if not GITHUB_TOKEN:
        return "GITHUB_TOKEN is missing. Cannot process any requests."

    try:
        g = Github(GITHUB_TOKEN)
        user = g.get_user()
        repo = user.get_repo(repo_name)

        # Set up context for existing repository
        context['project_name'] = repo_name
        context['repo_url'] = repo.clone_url
        context['repo_ssh_url'] = repo.ssh_url
        context['repo_html_url'] = repo.html_url

        return f"Successfully set up existing repository '{repo_name}'. Ready for clone and merge operations."

    except Exception as e:
        return f"Failed to access repository '{repo_name}': {e}"

@mcp.tool
def get_project_name(name: str) -> str:
    """Alias for set_project_name - Set a project name for use in subsequent commands."""
    context['project_name'] = name
    return f"Project name set to {name}"

@mcp.tool
def create_repository() -> str:
    """Create a new GitHub repository with the stored project name."""
    if not GITHUB_TOKEN:
        return "GITHUB_TOKEN is missing. Cannot process any requests."

    if not github_client or not github_user:
        return "GitHub client not initialized. Check your GITHUB_TOKEN."

    if 'project_name' not in context:
        return "No project name set. Use get_project_name first."

    project_name = context['project_name']

    try:
        # Create repository
        repo = github_user.create_repo(
            name=project_name,
            description=f"Repository for {project_name}",
            private=False,
            auto_init=True
        )

        context['repo_url'] = repo.clone_url
        context['repo_ssh_url'] = repo.ssh_url
        context['repo_html_url'] = repo.html_url

        return f"Repository {project_name} created successfully. URL: {repo.html_url}"

    except Exception as e:
        return f"Failed to create repository: {str(e)}"


@mcp.tool
def clone_repository() -> str:
    """Clone the repository to ./projects/<PROJECT_NAME>. Works with both new and existing repositories."""
    if not GITHUB_TOKEN:
        return "GITHUB_TOKEN is missing. Cannot process any requests."

    if 'project_name' not in context:
        return "No project name set. Use set_project_name first."

    project_name = context['project_name']

    # Check if repo_url is already set (from create_repository)
    if 'repo_url' not in context:
        # For existing repositories, construct the URL from project name
        try:
            g = Github(GITHUB_TOKEN)
            user = g.get_user()
            repo = user.get_repo(project_name)
            repo_url = repo.clone_url
            # Store the URLs in context for future use
            context['repo_url'] = repo_url
            context['repo_ssh_url'] = repo.ssh_url
            context['repo_html_url'] = repo.html_url
        except Exception as e:
            return f"Repository '{project_name}' not found or not accessible: {e}"
    else:
        repo_url = context['repo_url']

    # Create projects directory if it doesn't exist
    projects_dir = Path("./projects")
    projects_dir.mkdir(exist_ok=True)

    project_path = projects_dir / project_name

    # Remove existing directory if it exists (Windows-safe)
    if project_path.exists():
        success = _safe_rmtree(project_path)
        if not success:
            return f"Warning: Could not fully clean existing directory. Proceeding with clone..."

    # Clone repository
    success, output = _run_git_command([
        "git", "clone", "-b", "main", repo_url, str(project_path)
    ], Path.cwd())

    if success:
        context['project_path'] = project_path
        return f"Repository cloned to ./projects/{project_name}"
    else:
        return f"Failed to clone repository: {output}"

@mcp.tool
def merge_template_repository() -> str:
    """Clone React Vite template repository and merge its contents into the main project."""
    if not GITHUB_TOKEN:
        return "GITHUB_TOKEN is missing. Cannot process any requests."

    if 'project_path' not in context:
        return "No project path found. Clone repository first with clone_repository."

    project_path = context['project_path']

    # Create temporary directory for repo2
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir) / "react-vite"

        # Clone repo2
        success, output = _run_git_command([
            "git", "clone", REPO2_URL, str(temp_path)
        ], Path.cwd())

        if not success:
            return f"Failed to clone repo2: {output}"

        # Copy contents from repo2 to repo1 (excluding .git)
        try:
            for item in temp_path.iterdir():
                if item.name == '.git':
                    continue

                dest = project_path / item.name

                if item.is_dir():
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)

            return f"Repo2 merged into {context['project_name']}"

        except Exception as e:
            return f"Failed to merge repo2 contents: {str(e)}"
        

@mcp.tool
def create_file(file_path: str, content: str) -> str:
    """Create a file with specified content in the project directory."""
    if not GITHUB_TOKEN:
        return "GITHUB_TOKEN is missing. Cannot process any requests."

    if 'project_path' not in context:
        return "No project path found. Clone repository first with clone_repository."

    project_path = context['project_path']
    full_path = project_path / file_path

    try:
        # Create parent directories if they don't exist
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Write content to file
        full_path.write_text(content, encoding='utf-8')

        return f"File '{file_path}' created successfully at {full_path}"

    except Exception as e:
        return f"Failed to create file: {str(e)}"

@mcp.tool
def commit_and_push(commit_message: str) -> str:
    """Stage, commit, and push changes to the repository."""
    if not GITHUB_TOKEN:
        return "GITHUB_TOKEN is missing. Cannot process any requests."

    if 'project_path' not in context:
        return "No project path found. Clone repository first with clone_repository."

    project_path = context['project_path']

    # Get or construct repository URL
    if 'repo_url' not in context:
        if 'project_name' not in context:
            return "No repository URL or project name found. Set project name first."

        # Construct URL for existing repository
        project_name = context['project_name']
        try:
            g = Github(GITHUB_TOKEN)
            user = g.get_user()
            repo = user.get_repo(project_name)
            repo_url = repo.clone_url
            context['repo_url'] = repo_url
        except Exception as e:
            return f"Could not access repository '{project_name}': {e}"
    else:
        repo_url = context['repo_url']

    # Construct authenticated URL
    auth_url = repo_url.replace('https://', f'https://{GITHUB_TOKEN}@')

    commands = [
        ["git", "add", "."],
        ["git", "commit", "-m", commit_message],
        ["git", "remote", "set-url", "origin", auth_url],
        ["git", "push", "-u", "origin", "main"]
    ]

    for command in commands:
        success, output = _run_git_command(command, project_path)
        if not success:
            return f"Failed to push code: {output}"

    return f"Changes pushed to {context['project_name']} successfully"

@mcp.tool
def push_code(commit_message: str) -> str:
    """Alias for commit_and_push - Stage, commit, and push changes to the repository."""
    if not context.get('project_name'):
        return "Error: No project name set. Use set_project_name first."

    project_dir = os.path.join("projects", context['project_name'])
    if not os.path.exists(project_dir):
        return f"Error: Project directory {project_dir} does not exist. Clone the repository first."

    try:
        # Change to project directory
        original_dir = os.getcwd()
        os.chdir(project_dir)

        # Stage all changes
        subprocess.run(["git", "add", "."], check=True, capture_output=True, text=True)

        # Commit changes
        subprocess.run(["git", "commit", "-m", commit_message], check=True, capture_output=True, text=True)

        # Push changes
        result = subprocess.run(["git", "push"], check=True, capture_output=True, text=True)

        # Return to original directory
        os.chdir(original_dir)

        return f"Successfully committed and pushed changes with message: '{commit_message}'"

    except subprocess.CalledProcessError as e:
        # Return to original directory in case of error
        if 'original_dir' in locals():
            os.chdir(original_dir)
        return f"Git operation failed: {e.stderr if e.stderr else str(e)}"
    except Exception as e:
        # Return to original directory in case of error
        if 'original_dir' in locals():
            os.chdir(original_dir)
        return f"Error during commit and push: {e}"

@mcp.tool
def read_file_content(file_path: str) -> str:
    """Display the content of a file in the project directory."""
    if not GITHUB_TOKEN:
        return "GITHUB_TOKEN is missing. Cannot process any requests."

    if 'project_path' not in context:
        return "No project path found. Clone repository first with clone_repository."

    project_path = context['project_path']
    full_path = project_path / file_path

    try:
        if not full_path.exists():
            return f"File {file_path} does not exist"

        content = full_path.read_text(encoding='utf-8')
        return f"File content: {content}"

    except Exception as e:
        return f"Failed to read file: {str(e)}"

@mcp.tool
def check_file(file_path: str) -> str:
    """Alias for read_file_content - Display the content of a file in the project directory."""
    if not context.get('project_name'):
        return "Error: No project name set. Use set_project_name first."

    project_dir = os.path.join("projects", context['project_name'])
    full_path = os.path.join(project_dir, file_path)

    try:
        with open(full_path, 'r', encoding='utf-8') as file:
            content = file.read()
            return f"Content of {file_path}:\n\n{content}"
    except FileNotFoundError:
        return f"Error: File {file_path} not found in project directory."
    except Exception as e:
        return f"Error reading file {file_path}: {e}"

if __name__ == "__main__":
    # Configure logging (optional but recommended)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Check for GitHub Token at startup
    if not GITHUB_TOKEN:
       logging.critical("GITHUB_TOKEN is not set. The server cannot communicate with the GitHub API.")
       # Optionally exit here if the token is absolutely required
       # import sys
       # sys.exit("GitHub Token missing. Exiting.")

    # Initialize and run the server
    mcp.run(transport='stdio')
