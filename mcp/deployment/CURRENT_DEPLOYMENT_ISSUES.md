# Current MCP Deployment Issues Documentation

## Overview
This document catalogs the critical issues, pain points, and challenges in the current ProEthica MCP server deployment setup as of June 8, 2025.

## Critical Issues Identified

### 1. Repository Structure Fragmentation
**Status**: 🔴 Critical  
**Impact**: High confusion, deployment failures, maintenance overhead

#### Problem Details
- **Multiple project locations**:
  - `/home/chris/proethica-repo/` - Main repository (git tracked)
  - `/home/chris/proethica-mcp/` - MCP deployment (not git tracked)
  - `/home/chris/mcp-server/` - Additional MCP location
  - References to `/var/www/proethica/` in documentation

#### Current State Evidence
```bash
# Git repository only exists in proethica-repo
/home/chris/proethica-repo/.git ✅
/home/chris/proethica-mcp/.git ❌ (not a git repository)

# Active MCP process running from proethica-mcp
chris  24157  python3 mcp/http_ontology_mcp_server.py
```

#### Impact
- Deployment scripts reference wrong paths
- Unable to track changes in active deployment
- Manual file copying required for updates
- Risk of configuration drift

### 2. Branch Divergence Crisis
**Status**: 🔴 Critical  
**Impact**: Deployment automation completely broken

#### Problem Details
- Documentation references `simple` branch being 457 commits ahead of `main`
- Deployment scripts expect different branches than what's available
- No clear indication of which branch is production-ready

#### Evidence from Documentation
- `deploy-mcp-simple-branch.sh` expects `simple` branch
- `DEPLOYMENT_STRATEGY_REVISED.md` mentions 436-457 commit divergence
- Scripts reference both `main`, `simple`, and `develop` branches inconsistently

#### Impact
- Automated deployments fail
- Manual deployments require branch guesswork
- Risk of deploying wrong code version

### 3. Environment Configuration Inconsistencies
**Status**: 🟡 Medium  
**Impact**: Potential runtime failures, hard to debug issues

#### Current Configuration Issues
```bash
# /home/chris/proethica-mcp/mcp.env
USE_MOCK_GUIDELINE_RESPONSES=true  # ⚠️ Mock mode in production?
ONTOLOGY_DIR=/home/chris/proethica-repo/ontologies  # Cross-directory dependency
DATABASE_URL=postgresql://postgres:PASS@localhost:5433/ai_ethical_dm
```

#### Problems
- Production environment using mock responses
- Cross-directory dependencies (`proethica-repo` → `proethica-mcp`)
- Hardcoded localhost database connections
- No environment separation (dev/staging/prod)

### 4. Process Management Inadequacies
**Status**: 🟡 Medium  
**Impact**: Poor reliability, no automatic recovery

#### Current Process State
```bash
# Manual process management
chris  24154  /bin/bash ./start-mcp.sh
chris  24157  python3 mcp/http_ontology_mcp_server.py
```

#### Problems
- No systemd service management
- Manual startup scripts only
- No automatic restart on failure
- No proper process monitoring
- Logs scattered across multiple files

### 5. Security and Access Control Issues
**Status**: 🟡 Medium  
**Impact**: Security vulnerabilities, maintenance difficulties

#### Security Scan from Logs
```
# Multiple vulnerability scans detected in logs:
127.0.0.1 "GET /.git/config HTTP/1.0" 404
127.0.0.1 "GET /.env.save HTTP/1.0" 404
# ... 30+ lines of PHP vulnerability scans
```

#### Problems
- MCP server exposed to internet without proper security
- No fail2ban or intrusion detection
- User-space deployment (chris user) instead of dedicated service user
- Potential exposure of sensitive configuration files

### 6. Deployment Script Inconsistencies
**Status**: 🟡 Medium  
**Impact**: Unreliable deployments, manual intervention required

#### Available Scripts Analysis
```bash
deploy-droplet.sh          # 4045 bytes - Initial setup
deploy-mcp-manual.sh       # 6049 bytes - Manual deployment (executable)
deploy-mcp-production.sh   # 9452 bytes - Production deployment (executable)
deploy-mcp-simple-branch.sh # 9461 bytes - Simple branch specific (executable)
```

#### Problems
- Multiple deployment scripts with unclear purposes
- No clear indication which script to use when
- Scripts reference different directory structures
- No automated testing of deployment scripts

### 7. Monitoring and Health Check Gaps
**Status**: 🟡 Medium  
**Impact**: Poor visibility into system health

#### Current Monitoring
- Basic HTTP health endpoint exists
- Manual log checking required
- No automated alerting
- No performance metrics collection

#### Missing
- Automated health monitoring
- Performance metrics
- Error rate tracking
- Capacity monitoring
- Automated alerting

## Pain Points for Operators

### Daily Operations
1. **Unclear deployment process** - Multiple scripts, uncertain which to use
2. **Manual process management** - No systemd, manual start/stop
3. **Log management** - Logs in multiple locations, no rotation
4. **Health checking** - Manual curl commands to verify operation

### Troubleshooting
1. **Multiple source locations** - Changes could be in any directory
2. **Branch confusion** - Unclear which code is actually running
3. **Environment debugging** - Config spread across multiple files
4. **Process debugging** - No structured logging or monitoring

### Updates and Changes
1. **Manual file copying** - No git-based deployment to active location
2. **No rollback capability** - Manual process to revert changes
3. **Testing difficulties** - No staging environment
4. **Downtime required** - No zero-downtime deployment

## Impact Assessment

### High Impact Issues
- **Repository fragmentation** → Deployment confusion, manual errors
- **Branch divergence** → Broken automation, wrong code deployment
- **Security exposure** → Vulnerability scans, potential breaches

### Medium Impact Issues
- **Process management** → Poor reliability, manual intervention
- **Environment config** → Runtime failures, debugging difficulties
- **Monitoring gaps** → Poor visibility, delayed issue detection

### Low Impact Issues
- **Documentation drift** → Confusion, onboarding difficulties
- **Script redundancy** → Maintenance overhead

## Immediate Risks

### Deployment Risks
- **Wrong code deployment** due to branch confusion
- **Configuration drift** between documentation and reality
- **Manual errors** in file copying and process management

### Security Risks
- **Exposed MCP server** with vulnerability scanning attempts
- **User-space deployment** without proper isolation
- **Hardcoded credentials** in configuration files

### Operational Risks
- **Single point of failure** with manual process management
- **No disaster recovery** capability
- **Poor debugging** when issues occur

## Next Steps Required

### Immediate (This Week)
1. ✅ Document current state (this document)
2. 🔄 Identify which branch is actually production
3. 🔄 Consolidate repository structure
4. 🔄 Create emergency rollback procedure

### Short Term (Next 2 Weeks)
1. Implement proper systemd service
2. Standardize deployment location
3. Create staging environment
4. Fix branch divergence issue

### Long Term (Next Month)
1. Implement automated CI/CD
2. Add comprehensive monitoring
3. Security hardening
4. Documentation consolidation

---
**Last Updated**: June 8, 2025  
**Severity**: Critical deployment infrastructure issues requiring immediate attention  
**Priority**: High - impacts daily operations and introduces significant risk