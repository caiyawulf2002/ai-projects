#!/bin/bash
# ============================================================
# ai-projects repo scaffolding script
# Run this ONCE from your current personal-tutor parent directory
# ============================================================
# 
# BEFORE RUNNING:
# 1. cd to the folder that CONTAINS your personal-tutor/ directory
# 2. Run: bash setup-repo.sh
#
# WHAT THIS DOES:
# - Creates ai-projects/ as your new monorepo root
# - Moves personal-tutor/ → ai-projects/p1-personal-tutor/
# - Creates empty folders for P2–P5
# - Creates placeholder files so Git tracks the folders
# - Initializes a git repo (if not already one)
# ============================================================

set -e

echo "Setting up ai-projects monorepo..."

# Create root directory
mkdir -p ai-projects

# Move existing personal-tutor
if [ -d "personal-tutor" ]; then
    echo "Moving personal-tutor/ → ai-projects/p1-personal-tutor/"
    mv personal-tutor ai-projects/p1-personal-tutor
else
    echo "No personal-tutor/ found — creating empty p1-personal-tutor/"
    mkdir -p ai-projects/p1-personal-tutor
fi

# Scaffold remaining project directories
for dir in \
    "p2-domain-intelligence" \
    "p3-statements-analyzer" \
    "p4-portfolio-optimizer" \
    "p5-comps-agent"
do
    mkdir -p "ai-projects/$dir/src"
    mkdir -p "ai-projects/$dir/tests"
    mkdir -p "ai-projects/$dir/notebooks"
    mkdir -p "ai-projects/$dir/infra"
    touch "ai-projects/$dir/.gitkeep"
    echo "Created ai-projects/$dir/"
done

# Create root .gitignore
cat > ai-projects/.gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.venv/
venv/
.env
*.env

# Jupyter
.ipynb_checkpoints/

# GCP credentials — NEVER commit these
*.json
service-account*.json
application_default_credentials.json

# Local DBs
*.db
*.sqlite

# Docker
.dockerignore

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db

# Model artifacts (large files go in GCS, not git)
*.pkl
*.joblib
*.h5
*.pt
*.pth
models/
artifacts/
EOF

echo "Created .gitignore"

# Init git if not already a repo
cd ai-projects
if [ ! -d ".git" ]; then
    git init
    echo "Initialized git repo"
fi

echo ""
echo "======================================================="
echo "Done! Your new structure:"
echo ""
echo "ai-projects/"
echo "├── .claude/           ← Claude Code memory (already created)"
echo "├── .gitignore"
echo "├── p1-personal-tutor/ ← your existing code is here"
echo "├── p2-domain-intelligence/"
echo "├── p3-statements-analyzer/"
echo "├── p4-portfolio-optimizer/"
echo "└── p5-comps-agent/"
echo ""
echo "Next steps:"
echo "1. Copy the .claude/ folder from wherever you saved it into ai-projects/"
echo "2. cd ai-projects"
echo "3. git add . && git commit -m 'init: monorepo scaffold'"
echo "4. Create GitHub repo 'ai-projects' and push"
echo "5. Open Claude Code from the ai-projects/ root"
echo "======================================================="
