# Pandora

A self-hosted media organizer for videos, images, and web links.

## Features
- 📁 Media indexing and categorization
- 🏷️ Tagging system with nested tags
- 🔍 Advanced search and filtering
- 🌐 Web link archiving
- 📱 Responsive design for mobile, desktop, and TV

## Quick Start
```bash
# Clone repository
git clone https://github.com/yourusername/pandora.git
cd pandora

# Setup with Docker
docker-compose up -d

# Or manual setup
cd backend
pip install -r requirements/dev.txt
uvicorn app.main:app --reload

## Documentation
[API Docs](/docs)
[Development Guide](docs/development.md)

### 2. **.gitignore** (Wichtige Einträge)
```gitignore
# Python
__pycache__/
*.py[cod]
.env
.venv/
venv/

# Node
node_modules/
npm-debug.log*

# Media & Database
media/       # User media files
*.db
*.sqlite3

# IDE
.vscode/
.idea/
*.swp