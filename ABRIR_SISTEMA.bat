@echo off
title Speedy Cell ERP
cd /d "%~dp0"
echo ========================================================
echo        INICIANDO O SISTEMA SPEEDY CELL ERP...
echo ========================================================
python -m streamlit run Sistema_Speedy_Cell.py --server.headless=false
if %errorlevel% neq 0 (
    py -m streamlit run Sistema_Speedy_Cell.py --server.headless=false
)
pause
