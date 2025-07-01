# GitHub MCP Server

A Model Context Protocol (MCP) server for GitHub repository management using FastMCP.

## Features

- Create and manage GitHub repositories
- Clone repositories and manage files
- Support for both new and existing repositories
- Professional function naming with backward-compatible aliases
- Comprehensive error handling and timeout protection

## Tools Available

### Core Functions
- `set_project_name` - Set project name for repository operations
- `setup_existing_repository` - Set up context for existing repositories
- `create_repository` - Create new GitHub repository
- `clone_repository` - Clone repository locally
- `merge_template_repository` - Merge template with existing repository
- `create_file` - Create files in repository
- `read_file_content` - Read file content from repository
- `commit_and_push` - Commit and push changes

### Alias Functions (Backward Compatibility)
- `get_project_name` - Alias for set_project_name
- `make_repo` - Alias for create_repository
- `check_file` - Alias for read_file_content
- `push_code` - Alias for commit_and_push

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create `.env` file from template:
   ```bash
   cp .env.example .env
   ```

3. Add your GitHub Personal Access Token to `.env`:
   ```
   GITHUB_TOKEN=your_github_token_here
   ```

## Usage with MCP Inspector

Run the server with MCP Inspector for testing and development:

```bash
python github_mcp.py
```

## Requirements

- Python 3.10+
- GitHub Personal Access Token with `repo` and `user` scopes
- FastMCP 2.9.2+
- PyGitHub

## License

MIT License
# website-mcp
