# GitHub Actions Status Badges

Add these badges to your README.md to show the status of your CI/CD workflows:

## Deployment Status
```markdown
[![Deploy MCP Server](https://github.com/YOUR_USERNAME/ai-ethical-dm/actions/workflows/deploy-mcp.yml/badge.svg)](https://github.com/YOUR_USERNAME/ai-ethical-dm/actions/workflows/deploy-mcp.yml)
```

## Test Status
```markdown
[![Test MCP Server](https://github.com/YOUR_USERNAME/ai-ethical-dm/actions/workflows/test-mcp.yml/badge.svg)](https://github.com/YOUR_USERNAME/ai-ethical-dm/actions/workflows/test-mcp.yml)
```

## Docker Build Status
```markdown
[![Build MCP Docker](https://github.com/YOUR_USERNAME/ai-ethical-dm/actions/workflows/build-mcp-docker.yml/badge.svg)](https://github.com/YOUR_USERNAME/ai-ethical-dm/actions/workflows/build-mcp-docker.yml)
```

## Monitoring Status
```markdown
[![Monitor MCP Server](https://github.com/YOUR_USERNAME/ai-ethical-dm/actions/workflows/monitor-mcp.yml/badge.svg)](https://github.com/YOUR_USERNAME/ai-ethical-dm/actions/workflows/monitor-mcp.yml)
```

## All Badges Combined

Add this to the top of your README.md (replace YOUR_USERNAME with your GitHub username):

```markdown
# ProEthica AI Ethical Decision Making

[![Deploy MCP Server](https://github.com/YOUR_USERNAME/ai-ethical-dm/actions/workflows/deploy-mcp.yml/badge.svg)](https://github.com/YOUR_USERNAME/ai-ethical-dm/actions/workflows/deploy-mcp.yml)
[![Test MCP Server](https://github.com/YOUR_USERNAME/ai-ethical-dm/actions/workflows/test-mcp.yml/badge.svg)](https://github.com/YOUR_USERNAME/ai-ethical-dm/actions/workflows/test-mcp.yml)
[![Build MCP Docker](https://github.com/YOUR_USERNAME/ai-ethical-dm/actions/workflows/build-mcp-docker.yml/badge.svg)](https://github.com/YOUR_USERNAME/ai-ethical-dm/actions/workflows/build-mcp-docker.yml)
[![Monitor MCP Server](https://github.com/YOUR_USERNAME/ai-ethical-dm/actions/workflows/monitor-mcp.yml/badge.svg)](https://github.com/YOUR_USERNAME/ai-ethical-dm/actions/workflows/monitor-mcp.yml)
```

## Custom Badge for Specific Branch

To show the status of a specific branch:

```markdown
[![Deploy MCP Server](https://github.com/YOUR_USERNAME/ai-ethical-dm/actions/workflows/deploy-mcp.yml/badge.svg?branch=develop)](https://github.com/YOUR_USERNAME/ai-ethical-dm/actions/workflows/deploy-mcp.yml)
```

## Badge Colors

- **Green**: Workflow passing
- **Red**: Workflow failing
- **Yellow**: Workflow in progress
- **Gray**: No runs yet

## Live Server Status Badge

You can also create a custom badge for live server status using shields.io:

```markdown
![MCP Server Status](https://img.shields.io/endpoint?url=https://mcp.proethica.org/health/badge)
```

(This requires implementing a badge endpoint in your MCP server)