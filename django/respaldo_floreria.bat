@echo off
set "MYSQL=C:\Program Files\MySQL\MySQL Server 8.0\bin"
set "MONGO=C:\mongo-tools"
set "BACKUPDIR=C:\backups\flores_personalizados"

for /f "tokens=2 delims==" %%G in ('wmic os get LocalDateTime /value 2^>nul') do set DT=%%G
if defined DT (
    set FECHA=%DT:~0,8%
) else (
    set FECHA=%date:~10,4%%date:~4,2%%date:~7,2%
)

if not exist "%BACKUPDIR%" mkdir "%BACKUPDIR%"

echo ============================================
echo    SISTEMA DE BACKUP - FLORERIA
echo ============================================
echo [1/2] Respaldando MySQL...
"%MYSQL%\mysqldump.exe" -u floreria_app -pF10r3r1a_S3cur3! --no-tablespaces db_flores_personalizacion > "%BACKUPDIR%\mysql_%FECHA%.sql"

echo [2/2] Respaldando MongoDB...
"%MONGO%\mongodump.exe" --db local --out "%BACKUPDIR%\mongo_%FECHA%"

echo ============================================
echo    Backup completado: %BACKUPDIR%
echo    Archivo: mysql_%FECHA%.sql
echo ============================================
pause