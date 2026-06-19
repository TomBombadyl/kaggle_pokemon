@echo off
REM One-click fetch of the Simulation engine + sample_submission into .\data\sim
cd /d "%~dp0.."
echo Installing kagglehub (one-time)... > data\sim_fetch.log 2>&1
python -m pip install --quiet --upgrade kagglehub >> data\sim_fetch.log 2>&1
echo Fetching simulation engine... >> data\sim_fetch.log 2>&1
python "scripts\fetch_sim_engine.py" >> data\sim_fetch.log 2>&1
echo EXITCODE %ERRORLEVEL% >> data\sim_fetch.log 2>&1
echo Done. Log: data\sim_fetch.log
type data\sim_fetch.log
pause
