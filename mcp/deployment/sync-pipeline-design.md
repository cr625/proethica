# MCP Server Deployment Pipeline Design

## Current State Analysis

### Existing Infrastructure
- **Production Server**: mcp.proethica.org (port 5002)
- **Current Deployment**: Manual deployment in `/home/chris/proethica/` 
- **MCP Server File**: `mcp/enhanced_ontology_server_with_guidelines.py`
- **Existing Scripts**: Basic droplet deployment script available
- **GitHub Actions**: Disabled workflow exists for main app deployment

### Sync Challenges Identified
1. **No automated MCP-specific deployment**: Current GitHub Actions only handles main app
2. **Manual file copying**: Changes require manual SSH and file updates
3. **No health checks**: No automated verification of MCP server status
4. **Missing dependency management**: MCP requirements may differ from main app
5. **No rollback mechanism**: If deployment fails, manual intervention required

## Proposed Automated Sync Pipeline

### 1. Git-Based Deployment Strategy

```bash
# Production directory structure
/home/chris/proethica/
├── ai-ethical-dm/           # Main app repo
├── mcp-server/             # Dedicated MCP server directory
│   ├── current/            # Current active version
│   ├── releases/           # Versioned releases
│   └── shared/            # Shared configuration
```

### 2. Deployment Triggers

#### Automatic Triggers
- **Push to main branch** with changes in `mcp/` directory
- **Tagged releases** (v1.0.0, v1.1.0, etc.)

#### Manual Triggers  
- **GitHub Actions workflow dispatch**
- **Deploy script execution** from local development

### 3. Pipeline Stages

#### Stage 1: Pre-deployment Checks
- Validate MCP server syntax
- Check ontology files integrity
- Verify required environment variables
- Test MCP server startup locally

#### Stage 2: Deployment
- Create new release directory
- Copy MCP files to production
- Install/update Python dependencies
- Update configuration files
- Restart MCP service with zero-downtime

#### Stage 3: Health Verification
- Wait for MCP server startup
- Perform health check API calls
- Validate ontology endpoints
- Test guideline analysis functionality

#### Stage 4: Cleanup/Rollback
- Remove old releases (keep last 3)
- On failure: automatic rollback to previous version
- Send deployment notifications

### 4. Zero-Downtime Deployment

```bash
# Blue-Green deployment approach
1. Start new MCP server on alternate port (5003)
2. Verify new server health
3. Update nginx to point to new port
4. Stop old server
5. Move new server to primary port (5002)
```

### 5. Configuration Management

#### Environment Variables
- Separate `.env.production` for production-specific settings
- Encrypted secrets management via GitHub Secrets
- Database connection pooling configuration

#### Service Management
- Systemd service definition for auto-restart
- Process monitoring with health checks
- Log rotation and management

### 6. Monitoring and Alerting

#### Health Checks
- HTTP endpoint: `GET /health`
- Ontology availability: `GET /ontology/status`
- Database connectivity check
- Memory and CPU usage monitoring

#### Alerting
- Slack/Discord notifications on deployment
- Email alerts on deployment failures
- Performance degradation warnings

## Implementation Priority

### Phase 1: Basic Automation (Week 1)
1. Create MCP-specific GitHub Actions workflow
2. Implement basic health checks
3. Set up automated file sync

### Phase 2: Enhanced Pipeline (Week 2)
1. Add zero-downtime deployment
2. Implement rollback mechanism
3. Create monitoring dashboard

### Phase 3: Advanced Features (Week 3)
1. Add automated testing pipeline
2. Implement performance monitoring
3. Set up alerting system

## Security Considerations

- **API Key Management**: Rotate keys regularly, store in GitHub Secrets
- **Access Control**: Limit SSH access, use deploy keys
- **Network Security**: Firewall rules, fail2ban configuration
- **Audit Logging**: Track all deployment activities

## Rollback Strategy

1. **Automatic Rollback Triggers**:
   - Health check failures after deployment
   - High error rate detection
   - Manual trigger via GitHub Actions

2. **Rollback Process**:
   - Stop current MCP server
   - Restore previous release files
   - Restart with previous configuration
   - Verify rollback success

3. **Data Consistency**:
   - Database migrations handled separately
   - Configuration file versioning
   - Ontology file backup before updates