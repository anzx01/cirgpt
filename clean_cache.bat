@echo off
cd /d G:\myaist\cirgpt

echo Cleaning Python cache files...
cd backend
for /d /r . %%d in (__pycache__) do @if exist "%%d" (
    rmdir /s /q "%%d" 2>nul
)

cd ..\ai_service
for /d /r . %%d in (__pycache__) do @if exist "%%d" (
    rmdir /s /q "%%d" 2>nul
)

cd ..
echo Cleaning Next.js cache...
if exist "frontend\.next" rmdir /s /q "frontend\.next" 2>nul

echo Cleanup complete!
