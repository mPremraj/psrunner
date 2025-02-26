@echo off
REM Check if virtual environment folder exists
IF NOT EXIST venv (
    echo Creating virtual environment...
    python -m venv venv
)

echo Activating virtual environment...
call venv\Scripts\activate

echo Installing requirements...
python.exe -m pip install --upgrade pip
pip install --upgrade pip
pip install -r requirements.txt

echo Virtual environment setup complete.
echo To activate the environment later, run: venv\Scripts\activate
