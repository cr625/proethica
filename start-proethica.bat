@echo off
echo === ProEthica Windows Starter ===
echo Starting ProEthica with Windows environment...

REM Check if virtual environment exists, if not create it
if not exist venv (
    echo Virtual environment not found. Creating a new one...
    python -m venv venv
    if %ERRORLEVEL% NEQ 0 (
        echo Failed to create virtual environment. Make sure Python is installed and in PATH.
        echo Python 3.8 or higher is recommended.
        pause
        exit /b 1
    ) else (
        echo Virtual environment created successfully.
    )
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate
if %ERRORLEVEL% NEQ 0 (
    echo Failed to activate virtual environment.
    pause
    exit /b 1
)
echo Virtual environment activated.

REM Check and install Python dependencies
echo Checking Python dependencies...
python -c "import flask" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Flask not found. Installing core dependencies first...
    
    echo Installing Flask and core web dependencies...
    pip install flask flask-sqlalchemy flask-migrate flask-login flask-wtf python-dotenv werkzeug psycopg2-binary
    
    echo Installing RDF/MCP dependencies...
    pip install rdflib aiohttp requests gunicorn
    
    echo Installing API Integration dependencies...
    pip install anthropic>=0.50.0
    
    echo Installing document processing...
    pip install PyPDF2 python-docx beautifulsoup4
    
    echo Note: Some dependencies like chromadb with vector embeddings may require additional setup.
    echo You can install them manually if needed with:
    echo pip install -r requirements.txt
    
    echo Installed core dependencies. Continuing with setup...
) else (
    echo Flask already installed. Skipping dependency installation.
)

REM Set environment variable to force Windows environment
set ENVIRONMENT=windows

REM Create .env file if it doesn't exist
if not exist .env (
    echo No .env file found. Creating one from .env.example...
    copy .env.example .env
    echo Adding Windows-specific settings to .env file...
    echo MCP_SERVER_URL=http://localhost:5001 >> .env
    echo USE_MOCK_FALLBACK=false >> .env
    echo ENVIRONMENT=windows >> .env
    echo PUPPETEER_EXECUTABLE_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe >> .env
)

REM Check if Docker is installed
where docker >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Docker is not installed or not in PATH. Skipping Docker checks.
    goto :skip_docker
)

REM Check Docker container
echo Checking Docker and PostgreSQL container...
set POSTGRES_CONTAINER=postgres17-pgvector-windows
set DB_PORT=5433

REM Check if container exists
docker ps -a --filter "name=%POSTGRES_CONTAINER%" --format "{{.Status}}" >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo PostgreSQL container '%POSTGRES_CONTAINER%' not found.
    echo Creating new PostgreSQL container with pgvector...
    
    if exist postgres.Dockerfile (
        echo Using custom Dockerfile to build PostgreSQL with pgvector...
        docker build -t pgvector-custom -f postgres.Dockerfile .
        if %ERRORLEVEL% EQU 0 (
            docker run -d --name %POSTGRES_CONTAINER% -p %DB_PORT%:5432 -e POSTGRES_PASSWORD=PASS -e POSTGRES_DB=ai_ethical_dm pgvector-custom
            echo Waiting for PostgreSQL to initialize...
            timeout /t 5 /nobreak
        ) else (
            echo Failed to build Docker image. See error message above.
        )
    ) else (
        echo Using official pgvector image...
        docker run -d --name %POSTGRES_CONTAINER% -p %DB_PORT%:5432 -e POSTGRES_PASSWORD=PASS -e POSTGRES_DB=ai_ethical_dm pgvector/pgvector:pg17
        echo Waiting for PostgreSQL to initialize...
        timeout /t 5 /nobreak
        
        REM Initialize the vector extension
        echo Initializing pgvector extension...
        docker exec %POSTGRES_CONTAINER% psql -U postgres -d ai_ethical_dm -c "CREATE EXTENSION IF NOT EXISTS vector;"
    )
    
    REM Offer to restore from backup
    if exist backups\*.dump (
        echo Found database backups. Do you want to restore from the latest backup? (y/n)
        set /p restore_choice=
        if /i "%restore_choice%"=="y" (
            for /f "delims=" %%f in ('dir /b /od /a-d backups\*.dump') do set "LATEST_BACKUP=%%f"
            if defined LATEST_BACKUP (
                echo Restoring from backup: backups\%LATEST_BACKUP%
                if exist backups\docker_restore.sh (
                    REM Use the docker_restore.sh script with WSL bash
                    wsl bash ./backups/docker_restore.sh "backups/%LATEST_BACKUP%"
                ) else (
                    REM Manual restore
                    echo Copying backup file to Docker container...
                    docker cp "backups\%LATEST_BACKUP%" %POSTGRES_CONTAINER%:/tmp/backup.dump
                    
                    echo Restoring database from backup...
                    docker exec -it %POSTGRES_CONTAINER% bash -c "pg_restore -U postgres -O -x -v -d ai_ethical_dm /tmp/backup.dump"
                    
                    echo Database restore completed.
                )
            ) else (
                echo No backup files found in backups directory.
            )
        )
    )
) else (
    REM Check if container is running
    for /f "delims=" %%a in ('docker ps --filter "name=%POSTGRES_CONTAINER%" --format "{{.Status}}"') do set "CONTAINER_STATUS=%%a"
    if not defined CONTAINER_STATUS (
        echo PostgreSQL container '%POSTGRES_CONTAINER%' exists but is not running. Starting it now...
        docker start %POSTGRES_CONTAINER%
        if %ERRORLEVEL% EQU 0 (
            echo PostgreSQL container started successfully on port %DB_PORT%.
            echo Waiting for PostgreSQL to initialize...
            timeout /t 3 /nobreak
        ) else (
            echo Failed to start PostgreSQL container. Please check Docker logs.
        )
    ) else (
        echo PostgreSQL container '%POSTGRES_CONTAINER%' is already running.
    )
)

:skip_docker

REM Stop any existing Python processes related to MCP server
echo Checking for running MCP server processes...
powershell -Command "Get-Process -Name python* -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*run_enhanced_mcp_server.py*' -or $_.CommandLine -like '*http_ontology_mcp_server.py*' -or $_.CommandLine -like '*ontology_mcp_server.py*' } | ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }"

REM Also check for processes using port 5001
echo Checking for processes using port 5001...
powershell -Command "Get-NetTCPConnection -LocalPort 5001 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"

REM Ensure DATABASE_URL is properly set in .env
echo Ensuring DATABASE_URL is correctly set for Windows...
powershell -Command "(Get-Content .env) -replace '^DATABASE_URL=.*', 'DATABASE_URL=postgresql://postgres:PASS@localhost:%DB_PORT%/ai_ethical_dm' | Set-Content .env" || echo Failed to update DATABASE_URL, but continuing...

REM Initialize database if needed - using a separate Python script approach
echo Checking if database initialization is needed...
if not exist "app\models\__pycache__" (
    echo Initializing database tables...
    echo from app import create_app > init_db_temp.py
    echo from app.models import db >> init_db_temp.py
    echo app = create_app() >> init_db_temp.py
    echo with app.app_context(): >> init_db_temp.py
    echo     db.create_all() >> init_db_temp.py
    python init_db_temp.py || echo Database initialization failed, but continuing...
    del init_db_temp.py
)

REM Start the MCP server
echo Starting enhanced MCP server on port 5001...
start cmd /c "python mcp\run_enhanced_mcp_server.py"
echo Waiting for MCP server to initialize...
timeout /t 5 /nobreak

REM Start the Flask development server in a new window to keep it running
echo Starting Flask development server...
start cmd /c "python run.py"
echo Server windows have been launched. Check the new terminal windows for the application.

echo.
echo ----------------------------
echo ProEthica startup complete!
echo ----------------------------
echo.
echo The application should now be running at http://localhost:3333
echo MCP server should be running at http://localhost:5001
echo.
echo If you encounter any issues:
echo 1. Check both terminal windows for error messages
echo 2. Ensure all dependencies are installed
echo 3. Verify Docker is running (if using PostgreSQL container)
echo 4. Check that port 3333 and 5001 are not already in use
echo.
pause
