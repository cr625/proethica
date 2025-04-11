#!/bin/bash
# Script to manage the Git workflow between dev and main branches with deployment
# This script helps with the recommended workflow:
# 1. Develop in dev branch
# 2. Merge to main when ready
# 3. Deploy main to production

set -e # Exit on any error

echo "======================================================"
echo "GIT WORKFLOW MANAGER"
echo "======================================================"
echo "This script helps manage the Git workflow between development"
echo "and production environments using a dev → main → production strategy."
echo ""

# Check current branch
CURRENT_BRANCH=$(git branch --show-current)
echo "Current branch: ${CURRENT_BRANCH}"
echo ""

# Present options
echo "Available actions:"
echo "1) Check status of dev and main branches"
echo "2) Switch to dev branch"
echo "3) Switch to main branch"
echo "4) Merge dev into main"
echo "5) Deploy main to production"
echo "6) Full workflow: merge dev → main → deploy"
echo ""
read -p "Select an action (1-6): " ACTION_CHOICE

case $ACTION_CHOICE in
    1)
        # Check status of branches
        echo ""
        echo "Status of dev branch:"
        git checkout dev
        git status
        git log -1
        
        echo ""
        echo "Status of main branch:"
        git checkout main
        git status
        git log -1
        
        echo ""
        # Return to original branch
        git checkout $CURRENT_BRANCH
        echo "Returned to $CURRENT_BRANCH branch"
        ;;
        
    2)
        # Switch to dev branch
        echo ""
        echo "Switching to dev branch..."
        
        # Check if dev branch exists
        if ! git rev-parse --verify dev &>/dev/null; then
            echo "dev branch doesn't exist. Creating it from main..."
            git checkout -b dev main
        else
            git checkout dev
        fi
        
        echo "Now on dev branch. Make your changes here."
        ;;
        
    3)
        # Switch to main branch
        echo ""
        echo "Switching to main branch..."
        git checkout main
        echo "Now on main branch."
        ;;
        
    4)
        # Merge dev into main
        echo ""
        echo "Merging dev branch into main..."
        
        # Check for uncommitted changes
        if [[ -n $(git status --porcelain) ]]; then
            echo "ERROR: You have uncommitted changes. Commit or stash them first."
            exit 1
        fi
        
        # Check if dev branch exists
        if ! git rev-parse --verify dev &>/dev/null; then
            echo "ERROR: dev branch doesn't exist."
            exit 1
        fi
        
        # Make sure we have latest changes
        echo "Fetching latest changes..."
        git fetch
        
        # Switch to main and merge
        git checkout main
        echo "Merging dev into main..."
        if git merge dev; then
            echo "Merge successful!"
            echo "Run 'git push origin main' to push changes to GitHub."
        else
            echo "Merge conflict! Resolve conflicts manually, then commit."
        fi
        ;;
        
    5)
        # Deploy main to production
        echo ""
        echo "Deploying main branch to production..."
        
        # Ensure we're on main
        if [[ "$CURRENT_BRANCH" != "main" ]]; then
            echo "Switching to main branch first..."
            git checkout main
        fi
        
        # Check for uncommitted changes
        if [[ -n $(git status --porcelain) ]]; then
            echo "ERROR: You have uncommitted changes on main. Commit them first."
            exit 1
        fi
        
        # Push to GitHub (optional but recommended)
        read -p "Push to GitHub first? (recommended) (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "Pushing to GitHub..."
            git push origin main
        fi
        
        # Run the deployment script
        echo "Running deployment script..."
        ./scripts/direct_sync.sh
        
        # Prompt to restart service
        echo ""
        echo "Deployment complete! Do you want to restart the service on the server?"
        read -p "(y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "Connecting to server..."
            ssh -t -i server_config/proethica_deployment_key chris@209.38.62.85 "echo 'Connected to server. To restart the service, run:'; echo 'sudo systemctl restart proethica'; bash -l"
        fi
        ;;
        
    6)
        # Full workflow
        echo ""
        echo "Running full workflow: merge dev → main → deploy"
        
        # Check for uncommitted changes
        if [[ -n $(git status --porcelain) ]]; then
            echo "ERROR: You have uncommitted changes. Commit or stash them first."
            exit 1
        fi
        
        # Check if dev branch exists
        if ! git rev-parse --verify dev &>/dev/null; then
            echo "ERROR: dev branch doesn't exist."
            exit 1
        fi
        
        # 1. Make sure we have the latest changes
        echo "Fetching latest changes..."
        git fetch
        
        # 2. Switch to main and merge from dev
        git checkout main
        echo "Merging dev into main..."
        if ! git merge dev; then
            echo "Merge conflict! Please resolve conflicts manually, then commit."
            exit 1
        fi
        
        # 3. Push to GitHub
        echo "Pushing to GitHub..."
        git push origin main
        
        # 4. Deploy to production
        echo "Deploying to production server..."
        ./scripts/direct_sync.sh
        
        # 5. Prompt to restart service
        echo ""
        echo "Deployment complete! Do you want to restart the service on the server?"
        read -p "(y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "Connecting to server..."
            ssh -t -i server_config/proethica_deployment_key chris@209.38.62.85 "echo 'Connected to server. To restart the service, run:'; echo 'sudo systemctl restart proethica'; bash -l"
        fi
        
        # 6. Return to dev branch for future development
        echo "Switching back to dev branch for continued development..."
        git checkout dev
        ;;
        
    *)
        echo "Invalid option."
        ;;
esac

echo ""
echo "======================================================"
echo "RECOMMENDED WORKFLOW:"
echo "======================================================"
echo "1. DEVELOP in the dev branch:"
echo "   git checkout dev"
echo "   ... make changes ..."
echo "   git add ."
echo "   git commit -m \"Your changes\""
echo ""
echo "2. When ready, MERGE to main branch:"
echo "   ./scripts/git_workflow.sh     # Option 4 or 6"
echo ""
echo "3. DEPLOY to production:"
echo "   ./scripts/direct_sync.sh"
echo ""
echo "4. If changes are made directly on the server, use:"
echo "   ./scripts/sync_from_production.sh"
echo "   ... to bring those changes back to your dev environment"
echo "======================================================"
