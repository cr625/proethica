# VSCode Launch Configurations Guide

## Updated Launch Configurations

### 🚀 Flask App - Local MCP
**Best for: Development with local MCP server**
- **Port**: 3333
- **MCP Server**: http://localhost:5001 (local)
- **Auth**: Bypassed for easy development
- **Database**: Local PostgreSQL
- **Access**: http://localhost:3333
- **Dashboard**: http://localhost:3333/dashboard

### 🌐 Flask App - Production MCP  
**Best for: Testing with production MCP server**
- **Port**: 3333
- **MCP Server**: https://mcp.proethica.org (production)
- **Auth**: Bypassed with production MCP capabilities
- **Database**: Local PostgreSQL
- **Access**: http://localhost:3333
- **Dashboard**: http://localhost:3333/dashboard

### 📊 ProEthica Dashboard - Development
**Best for: Dashboard-focused development and testing**
- **Special Features**: 
  - Displays startup information about dashboard features
  - Shows current system status and completion rates
  - Pre-configured for optimal dashboard experience
- **Port**: 3333
- **Auth**: Bypassed
- **Direct Dashboard Access**: http://localhost:3333/dashboard

### 🔐 ProEthica Dashboard - With Authentication
**Best for: Testing with real authentication**
- **Port**: 3333
- **Auth**: Enabled - requires login
- **Login Credentials**:
  - **Username**: admin
  - **Password**: password123
  - **Email**: admin@proethica.org
- **Access**: http://localhost:3333 (will redirect to login)
- **Dashboard**: http://localhost:3333/dashboard (after login)

### 🔧 MCP Server - Local
**Best for: Developing and debugging the MCP server**
- **Port**: 5001
- **Purpose**: Run MCP server locally for guideline analysis
- **Usage**: Start this first, then run one of the Flask configurations

### 🐍 Python: Current File
**Best for: Running individual Python scripts**
- **Updated**: Now includes BYPASS_AUTH for testing scripts
- **Environment**: Development with proper database configuration

## Key Environment Variables Set

All configurations now include:
- `BYPASS_AUTH=true` - Skip authentication for development
- `DEBUG=true` - Enable debug mode
- `ENVIRONMENT=development` - Development mode
- `SQLALCHEMY_DATABASE_URI` - Proper database connection
- `PYTHONPATH` - Ensures proper module imports

## Recommended Workflow

1. **For Dashboard Development**:
   - Use "ProEthica Dashboard - Development"
   - Navigate to http://localhost:3333/dashboard

2. **For General Development**:
   - Use "Flask App - Local MCP" 
   - Start local MCP server if needed with "MCP Server - Local"

3. **For Testing with Production MCP**:
   - Use "Flask App - Production MCP"
   - Gets real MCP capabilities without local server setup

## Dashboard URLs

Once any Flask configuration is running:
- **Main Dashboard**: http://localhost:3333/dashboard
- **World Dashboard**: http://localhost:3333/dashboard/world/1
- **Stats API**: http://localhost:3333/dashboard/api/stats
- **Workflow API**: http://localhost:3333/dashboard/api/workflow
- **Capabilities API**: http://localhost:3333/dashboard/api/capabilities

## Quick Start

1. **Select** "ProEthica Dashboard - Development" from VSCode debug panel
2. **Press F5** or click "Start Debugging"
3. **Wait** for startup messages in terminal
4. **Navigate** to http://localhost:3333/dashboard
5. **Explore** the unified dashboard with real system data!