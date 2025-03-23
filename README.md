# AI Ethical Decision-Making Simulator

A simulation platform for ethical decision-making in military medical triage scenarios, built with Flask, SQLAlchemy, LangChain, LangGraph, and Model Context Protocol.

## Overview

This project simulates event-based scenarios like military medical triage to train and evaluate ethical decision-making agents. The system combines rule-based reasoning with case-based and analogical reasoning from domain-specific ethical guidelines.

## Features

- Event-based simulation engine
- Character and resource management
- Decision tracking and evaluation
- Ethical reasoning framework
- Integration with LLMs via LangChain and LangGraph
- Model Context Protocol for extensibility
- Zotero integration for academic references and citations
- World and scenario reference management

## Architecture

The application is built with:

- **Backend**: Flask, SQLAlchemy, PostgreSQL
- **AI Components**: LangChain, LangGraph
- **Extension**: Model Context Protocol

## Setup

### Prerequisites

- Python 3.8+
- PostgreSQL
- OpenAI API key (for LLM integration)

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/cr625/ai-ethical-dm.git
   cd ai-ethical-dm
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set up the database:
   ```
   createdb -U postgres ai_ethical_dm
   ```

5. Create a `.env` file with your configuration:
   ```
   FLASK_APP=run.py
   FLASK_ENV=development
   SECRET_KEY=your-secret-key
   DATABASE_URL=postgresql://postgres:yourpassword@localhost/ai_ethical_dm
   OPENAI_API_KEY=your-openai-api-key
   
   # For Zotero integration (optional)
   ZOTERO_API_KEY=your-zotero-api-key
   ZOTERO_USER_ID=your-zotero-user-id
   ```
   
   See `ZOTERO_INTEGRATION.md` for more details on setting up the Zotero integration.

6. Initialize the database:
   ```
   export FLASK_APP="app:create_app"
   flask db upgrade
   ```

7. Run the application:
   ```
   python run.py
   ```

## Usage

1. Access the web interface at `http://localhost:5000`
2. Create scenarios with characters and resources
3. Run simulations and observe decision-making
4. Evaluate ethical outcomes

## License

GPL 3

## Contributors

- Christopher Rauch
