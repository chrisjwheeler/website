@echo off
setlocal

cd /d "%~dp0"

where bundle >nul 2>&1
if errorlevel 1 (
    echo Error: Ruby and Bundler are not installed.
    echo Run: winget install RubyInstallerTeam.RubyWithDevKit.3.3 --accept-source-agreements --accept-package-agreements
    echo Then restart your terminal and run: bundle install
    exit /b 1
)

echo Building twohalv.es...
bundle exec jekyll build
if errorlevel 1 exit /b 1

echo.
echo Serving at http://127.0.0.1:4000/
echo Press Ctrl-C to stop.
bundle exec jekyll serve --livereload
