@echo off
setlocal
cd /d "%~dp0"

echo ========================================================
echo        AI TEXT-TO-SPEECH ^& IELTS LISTENING STUDIO
echo ========================================================
echo.
echo Dang khoi dong giao dien Web Streamlit...
echo Trinh duyet se tu dong mo tai: http://localhost:8501
echo.

if exist "venv\Scripts\python.exe" (
    ".\venv\Scripts\python.exe" -m streamlit run app.py --browser.gatherUsageStats false
) else (
    python -m streamlit run app.py --browser.gatherUsageStats false
)

pause
