@echo off
chcp 65001 >nul

set "V8PATH=C:\Program Files\1cv8\8.3.27.1786\bin\1cv8.exe"
set "EXT_FILE=C:\1CProject\command-center-1c\storage\extensions\ТестовоеРасширение.cfe"
set "EXT_NAME=ТестовоеРасширение"
set "USER=ГлавБух"
set "PASS=22022"

echo ========================================
echo ТЕСТ УСТАНОВКИ РАСШИРЕНИЯ
echo ========================================
echo.
echo Файл расширения: %EXT_FILE%
echo Имя расширения: %EXT_NAME%
echo.

rem === Вариант 1: /S с localhost ===
echo Попытка 1: /S"localhost\Stroygrupp_7751284461"
"%V8PATH%" DESIGNER /DisableStartupMessages /DisableStartupDialogs /S"localhost\Stroygrupp_7751284461" /N"%USER%" /P"%PASS%" /LoadCfg "%EXT_FILE%" -Extension "%EXT_NAME%" /Out "test_v1.log"
if %errorlevel% equ 0 (
    echo ✅ Вариант 1 УСПЕШЕН!
    goto success
) else (
    echo ❌ Вариант 1 неудачен
    type test_v1.log
    echo.
)

rem === Вариант 2: /IBConnectionString ===
echo Попытка 2: /IBConnectionString
"%V8PATH%" DESIGNER /DisableStartupMessages /DisableStartupDialogs /IBConnectionString"Srvr=\"localhost\";Ref=\"Stroygrupp_7751284461\";" /N"%USER%" /P"%PASS%" /LoadCfg "%EXT_FILE%" -Extension "%EXT_NAME%" /Out "test_v2.log"
if %errorlevel% equ 0 (
    echo ✅ Вариант 2 УСПЕШЕН!
    goto success
) else (
    echo ❌ Вариант 2 неудачен
    type test_v2.log
    echo.
)

rem === Вариант 3: /F с localhost ===
echo Попытка 3: /F"localhost\Stroygrupp_7751284461"
"%V8PATH%" DESIGNER /DisableStartupMessages /DisableStartupDialogs /F"localhost\Stroygrupp_7751284461" /N"%USER%" /P"%PASS%" /LoadCfg "%EXT_FILE%" -Extension "%EXT_NAME%" /Out "test_v3.log"
if %errorlevel% equ 0 (
    echo ✅ Вариант 3 УСПЕШЕН!
    goto success
) else (
    echo ❌ Вариант 3 неудачен
    type test_v3.log
    echo.
)

echo ❌ Все варианты неудачны!
pause
exit /b 1

:success
echo.
echo ========================================
echo ✅ РАСШИРЕНИЕ УСТАНОВЛЕНО
echo ========================================
pause
exit /b 0
