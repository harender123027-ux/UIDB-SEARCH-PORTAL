@echo off
cd /d "%~dp0"
pm2 delete all
pm2 serve dist 5173 --name "uidb-frontend" --spa
pm2 start backend\start-backend.bat --name "uidb-backend"
pm2 save
