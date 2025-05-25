# Revised MCP Server Deployment Strategy

## Current Situation Analysis

### Critical Issues

1. **Branch Divergence**
   - Current branch (`simple`): 436 commits ahead of `main`
   - Main branch: Last updated months ago with deployment scripts
   - **Risk**: Deploying from main would deploy outdated code

2. **Directory Structure Mismatch**
   ```
   Production Server (proethica.org):
   ├── /var/www/proethica/          # Main web application
   │   └── ai-ethical-dm/           # Main app repository
   └── /home/chris/proethica/       # MCP server location
       ├── ai-ethical-dm/           # Full repository clone
       └── mcp-server/              # MCP deployment directory
   ```

3. **User Permission Issues**
   - Web app runs as `www-data` user in `/var/www/`
   - MCP server runs as `chris` user in home directory
   - Different permission requirements and security contexts

## Recommended Solutions

### Option 1: Merge Current Branch to Main (Recommended)

**Steps:**
1. Create comprehensive testing plan for 436 commits
2. Merge `simple` branch into `main` with careful review
3. Update deployment scripts to handle both locations
4. Deploy from unified main branch

**Pros:**
- Single source of truth
- Automated deployments work correctly
- Consistent codebase

**Cons:**
- Large merge effort required
- Risk of breaking changes
- Requires comprehensive testing

### Option 2: Deploy MCP from Current Branch

**Implementation:**
1. Update GitHub Actions to deploy from `simple` branch
2. Create branch-specific deployment workflow
3. Keep MCP server deployment separate from main app

```yaml
# .github/workflows/deploy-mcp-simple-branch.yml
on:
  push:
    branches: [ simple ]
    paths:
      - 'mcp/**'
```

**Pros:**
- Quick implementation
- No merge required
- Can start immediately

**Cons:**
- Divergent deployment processes
- Maintenance overhead
- Confusion about which branch to use

### Option 3: Separate MCP Repository

**Implementation:**
1. Extract MCP server to separate repository
2. Independent deployment pipeline
3. Link as submodule or separate service

**Pros:**
- Clean separation of concerns
- Independent versioning
- Simpler deployment

**Cons:**
- Code duplication
- Coordination overhead
- Breaking existing structure

## Revised Deployment Architecture

### Recommended Directory Structure

```bash
# Production Server Organization
/home/chris/
├── proethica/
│   ├── ai-ethical-dm/          # Full repository (simple branch)
│   └── mcp-production/         # MCP server deployment
│       ├── current/            # Active version symlink
│       ├── releases/           # Versioned releases
│       └── config/             # Production configs
└── deployment/
    └── scripts/                # Deployment automation

/var/www/proethica/
└── ai-ethical-dm/              # Main web app (if needed separately)
```

### Deployment Script Updates

```bash
#!/bin/bash
# Updated deployment script accounting for branch and directory

# Configuration
BRANCH="simple"  # Use simple branch instead of main
MCP_USER="chris"
MCP_HOME="/home/chris/proethica"
REPO_DIR="$MCP_HOME/ai-ethical-dm"

# Pull from correct branch
cd "$REPO_DIR"
git fetch origin
git checkout "$BRANCH"
git pull origin "$BRANCH"

# Continue with deployment...
```

## Immediate Action Plan

### Phase 1: Stabilize Current Setup (Week 1)

1. **Update deployment scripts for `simple` branch**
   ```bash
   # In deploy-mcp-manual.sh
   git checkout simple
   git pull origin simple
   ```

2. **Document current state**
   - Which branch is production using?
   - What's the actual deployment process?
   - Who has access and permissions?

3. **Create branch-aware health checks**
   ```bash
   # Check which branch is deployed
   ssh chris@proethica.org 'cd ~/proethica/ai-ethical-dm && git branch --show-current'
   ```

### Phase 2: Unify Deployment (Week 2-3)

1. **Plan branch reconciliation**
   - Identify critical changes in 436 commits
   - Test merge strategy
   - Create rollback plan

2. **Standardize directory structure**
   - Decide on final location for MCP
   - Update all scripts and configs
   - Test permissions and access

3. **Update CI/CD pipeline**
   - Make branch-aware deployments
   - Add deployment safeguards
   - Implement staging environment

### Phase 3: Long-term Solution (Month 2)

1. **Merge branches or separate repositories**
2. **Implement proper staging/production flow**
3. **Add comprehensive monitoring**

## Security Considerations

### Current Risks
- Different users for different components
- Home directory deployment (less secure)
- Manual permission management

### Recommended Improvements
1. **Dedicated service user**: Create `proethica-mcp` user
2. **Proper directory permissions**: Move to `/opt/proethica-mcp/`
3. **Systemd service**: Run as system service with limited permissions

## Updated Deployment Commands

### For Current Situation (Simple Branch)

```bash
# Manual deployment from simple branch
./deploy-mcp-manual-simple.sh production

# Health check with branch awareness
./health-check-with-branch.sh production

# Quick sync command
ssh chris@proethica.org '
  cd ~/proethica/ai-ethical-dm && 
  git checkout simple && 
  git pull origin simple && 
  cd ~/proethica/mcp-server/current &&
  pkill -f enhanced_ontology &&
  nohup python enhanced_ontology_server_with_guidelines.py &
'
```

## Recommendations

### Immediate (This Week)
1. **Update deployment scripts** to use `simple` branch
2. **Document actual production setup** 
3. **Create emergency deployment procedure**

### Short-term (Next Month)
1. **Plan branch merge strategy**
2. **Standardize deployment locations**
3. **Implement proper CI/CD**

### Long-term (Next Quarter)
1. **Unify codebase** (merge or separate)
2. **Professional deployment infrastructure**
3. **Full monitoring and alerting**

## Conclusion

The current setup is functional but fragile. The massive branch divergence and directory structure mismatch create deployment risks. I recommend:

1. **Immediately**: Update scripts to deploy from `simple` branch
2. **Soon**: Plan and execute branch reconciliation
3. **Long-term**: Professional deployment infrastructure

This ensures the MCP server stays in sync while addressing the fundamental issues in the deployment architecture.