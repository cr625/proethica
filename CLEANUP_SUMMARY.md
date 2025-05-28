# Deployment Cleanup Summary

## What Was Done

### 1. Cleaned Up server_config Directory
- **Archived** all outdated files to `server_config/archived/`:
  - Old systemd service files (referenced wrong paths)
  - Gunicorn-based scripts (no longer used)
  - Legacy configuration files
- **Updated** server_config/README.md to point to active deployment location
- **Kept** the directory structure for historical reference

### 2. Consolidated Documentation
- **Created** `/mcp/deployment/README_CONSOLIDATED.md` with complete deployment guide
- **Updated** `/mcp/deployment/README.md` to reference the consolidated guide
- **Removed** redundant documentation files

### 3. Identified Current State
- **Active deployment**: `/mcp/deployment/` directory
- **Production branch**: `simple` (457 commits ahead of main)
- **Development branch**: `guidelines-enhancement` (your current work)
- **Deployment scripts**: Work for `simple` branch, need adaptation for `guidelines-enhancement`

## Current Structure

```
ai-ethical-dm/
├── mcp/
│   └── deployment/              # ACTIVE deployment location
│       ├── README.md            # Points to consolidated guide
│       ├── README_CONSOLIDATED.md # Complete deployment documentation
│       ├── deploy-mcp-simple-branch.sh # Current deployment script
│       ├── health-check.sh      # Health monitoring
│       └── ...                  # Other deployment resources
└── server_config/               # LEGACY location
    ├── README.md                # Explains this is legacy
    └── archived/                # Old files for reference
```

## Next Steps

1. **Create deployment script for guidelines-enhancement branch**
   - Copy `deploy-mcp-simple-branch.sh`
   - Modify to use `guidelines-enhancement` branch
   - Test on production server

2. **Update production to use guidelines-enhancement**
   - Deploy to parallel instance first
   - Test thoroughly
   - Switch production when ready

3. **Consider branch strategy**
   - Eventually reconcile simple/main/guidelines-enhancement branches
   - Or maintain separate deployment tracks

## Key Takeaway

All active deployment processes are now in `/mcp/deployment/`. The `/server_config/` directory is legacy and should not be used for new deployments.