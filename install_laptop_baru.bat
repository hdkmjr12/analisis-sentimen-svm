@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Instalasi Analisis Sentimen SVM

echo ============================================================
echo   INSTALASI PROGRAM ANALISIS SENTIMEN SVM
echo ============================================================
echo.

set "PYTHON_EXE="
set "SQL_FILE=%CD%\database\analisis_svm_relasi.sql"
set "MYSQL_EXE="

if not exist "%SQL_FILE%" (
    echo [GAGAL] File database tidak ditemukan:
    echo %SQL_FILE%
    goto :gagal
)

echo [1/5] Mencari Python 3.12...
if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
    set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python312\python.exe"
)
if not defined PYTHON_EXE if exist "%ProgramFiles%\Python312\python.exe" (
    set "PYTHON_EXE=%ProgramFiles%\Python312\python.exe"
)
if not defined PYTHON_EXE (
    for /f "delims=" %%P in ('where python 2^>nul') do (
        if not defined PYTHON_EXE set "PYTHON_EXE=%%P"
    )
)

if defined PYTHON_EXE (
    "%PYTHON_EXE%" -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)" >nul 2>nul
    if errorlevel 1 set "PYTHON_EXE="
)

if not defined PYTHON_EXE (
    echo Python belum terpasang. Mencoba memasang Python 3.12 dengan winget...
    where winget >nul 2>nul
    if errorlevel 1 (
        echo [GAGAL] Python dan winget tidak ditemukan.
        echo Instal Python 3.12 dari https://www.python.org/downloads/
        echo Aktifkan pilihan "Add Python to PATH", lalu jalankan file ini lagi.
        goto :gagal
    )

    winget install --exact --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo [GAGAL] Instalasi Python melalui winget tidak berhasil.
        goto :gagal
    )

    if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
        set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python312\python.exe"
    )
)

if not defined PYTHON_EXE if exist "%ProgramFiles%\Python312\python.exe" (
    set "PYTHON_EXE=%ProgramFiles%\Python312\python.exe"
)
if not defined PYTHON_EXE (
    echo [GAGAL] Python sudah dipasang tetapi lokasinya belum ditemukan.
    echo Tutup jendela ini, lalu jalankan install_laptop_baru.bat kembali.
    goto :gagal
)

"%PYTHON_EXE%" -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)" >nul 2>nul
if errorlevel 1 (
    echo [GAGAL] Program membutuhkan Python 3.12.
    echo Python yang ditemukan:
    "%PYTHON_EXE%" --version
    echo Silakan instal Python 3.12 lalu jalankan installer kembali.
    goto :gagal
)
echo       Python ditemukan: %PYTHON_EXE%

echo.
echo [2/5] Menyiapkan pip pada Python 3.12...
"%PYTHON_EXE%" -m ensurepip --upgrade >nul 2>nul

echo.
echo [3/5] Menginstal seluruh library Python...
"%PYTHON_EXE%" -m pip install --upgrade pip
if errorlevel 1 goto :pip_gagal
"%PYTHON_EXE%" -m pip install -r "%CD%\requirements.txt"
if errorlevel 1 goto :pip_gagal

"%PYTHON_EXE%" -c "import sklearn, joblib, mysql.connector, Sastrawi, pandas; assert sklearn.__version__ == '1.8.0'; print('      Library utama berhasil diperiksa.')"
if errorlevel 1 goto :pip_gagal

echo.
echo [4/5] Mencari MySQL atau MariaDB...
call :cari_mysql
if not defined MYSQL_EXE (
    echo [GAGAL] mysql.exe tidak ditemukan.
    echo Instal XAMPP atau MySQL Server terlebih dahulu.
    echo Untuk XAMPP, lokasi yang didukung adalah C:\xampp.
    goto :gagal
)
echo       MySQL ditemukan: %MYSQL_EXE%

"%MYSQL_EXE%" --protocol=tcp -h 127.0.0.1 -u root -e "SELECT 1;" >nul 2>nul
if errorlevel 1 (
    if exist "C:\xampp\mysql_start.bat" (
        echo       MySQL belum aktif. Menjalankan MySQL XAMPP...
        start "MySQL XAMPP" /min "C:\xampp\mysql_start.bat"
        timeout /t 7 /nobreak >nul
    )
)

"%MYSQL_EXE%" --protocol=tcp -h 127.0.0.1 -u root -e "SELECT 1;" >nul 2>nul
if errorlevel 1 (
    echo [GAGAL] Tidak dapat terhubung ke MySQL.
    echo Pastikan MySQL aktif dan akun root tidak menggunakan password.
    echo Konfigurasi program saat ini: host=localhost, user=root, password kosong.
    goto :gagal
)

echo.
echo [5/5] Menyiapkan dan mengimpor database...
"%MYSQL_EXE%" --protocol=tcp -h 127.0.0.1 -u root -e "CREATE DATABASE IF NOT EXISTS analisis_svm_relasi CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
if errorlevel 1 (
    echo [GAGAL] Database tidak dapat dibuat.
    goto :gagal
)

set "DB_CHECK_FILE=%TEMP%\analisis_svm_db_check_%RANDOM%.txt"
"%MYSQL_EXE%" --protocol=tcp -h 127.0.0.1 -u root -N -s -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='analisis_svm_relasi';" > "%DB_CHECK_FILE%"
set "JUMLAH_TABEL=0"
set /p JUMLAH_TABEL=<"%DB_CHECK_FILE%"
del /q "%DB_CHECK_FILE%" >nul 2>nul

if "!JUMLAH_TABEL!"=="0" (
    echo       Mengimpor database. Proses ini dapat memerlukan beberapa saat...
    "%MYSQL_EXE%" --protocol=tcp -h 127.0.0.1 -u root --default-character-set=utf8mb4 analisis_svm_relasi < "%SQL_FILE%"
    if errorlevel 1 (
        echo [GAGAL] Impor database tidak selesai.
        goto :gagal
    )
    echo       Database berhasil diimpor.
) else (
    echo       Database sudah berisi !JUMLAH_TABEL! tabel. Impor dilewati agar data tidak tertimpa.
)

"%PYTHON_EXE%" -c "import sys; sys.path.insert(0, r'%CD%\cgi-bin'); from db_utils import buat_koneksi; k=buat_koneksi(); c=k.cursor(); c.execute('SELECT COUNT(*) FROM admin_users'); print('      Koneksi program berhasil. Admin ditemukan:', c.fetchone()[0]); c.close(); k.close()"
if errorlevel 1 (
    echo [GAGAL] Database ada, tetapi belum dapat dibaca oleh program.
    goto :gagal
)

echo.
echo ============================================================
echo   INSTALASI SELESAI
echo ============================================================
echo Jalankan "aktif server.bat" untuk membuka program.
echo.
pause
exit /b 0

:cari_mysql
if exist "C:\xampp\mysql\bin\mysql.exe" set "MYSQL_EXE=C:\xampp\mysql\bin\mysql.exe"
if not defined MYSQL_EXE (
    for /f "delims=" %%M in ('where mysql 2^>nul') do (
        if not defined MYSQL_EXE set "MYSQL_EXE=%%M"
    )
)
if not defined MYSQL_EXE (
    for /d %%D in ("%ProgramFiles%\MySQL\MySQL Server *") do (
        if exist "%%D\bin\mysql.exe" set "MYSQL_EXE=%%D\bin\mysql.exe"
    )
)
if not defined MYSQL_EXE (
    for /d %%D in ("%ProgramFiles%\MariaDB *") do (
        if exist "%%D\bin\mysql.exe" set "MYSQL_EXE=%%D\bin\mysql.exe"
    )
)
if not defined MYSQL_EXE (
    for /d %%D in ("C:\laragon\bin\mysql\mysql-*") do (
        if exist "%%D\bin\mysql.exe" set "MYSQL_EXE=%%D\bin\mysql.exe"
    )
)
exit /b 0

:pip_gagal
echo.
echo [GAGAL] Library Python tidak berhasil diinstal.
echo Pastikan laptop terhubung ke internet, lalu jalankan installer kembali.
goto :gagal

:gagal
echo.
echo Instalasi belum selesai.
pause
exit /b 1
