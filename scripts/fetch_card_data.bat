@echo off
REM One-click fetch of the PTCG card data into .\data using the stored token.
cd /d "%~dp0.."
echo Installing kagglehub (one-time)...
python -m pip install --quiet --upgrade kagglehub
echo.
echo Fetching card data...
python "scripts\fetch_card_data.py"
echo.
echo Finished. This window can be closed.
pause
