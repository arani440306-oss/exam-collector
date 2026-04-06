@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo [시험지 수집 캠페인] 서버 시작 중...
echo.

pip install -r requirements.txt -q

echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo  로컬 접속:  http://localhost:8000
echo  관리자:     http://localhost:8000/admin
echo  QR 코드:    http://localhost:8000/qr?host=YOUR_IP:8000
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.

python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pause
