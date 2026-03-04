# Installation

Full installation documentation is in the MkDocs site:

- **Online**: [proethica.org/docs/admin-guide/installation](https://proethica.org/docs/admin-guide/installation/)
- **Source**: [docs/admin-guide/installation.md](docs/admin-guide/installation.md)

## Quick Start

```bash
git clone https://github.com/cr625/proethica.git
cd proethica

python3 -m venv venv-proethica
source venv-proethica/bin/activate
pip install -r requirements.txt
cp .env.production.example .env
# Edit .env with your database and API credentials
python run.py
```

Access at: http://localhost:5000
