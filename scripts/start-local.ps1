# JobAgent v2 本地一键启动（PowerShell，无需 Docker）
# 用法：
#   .\scripts\start-local.ps1            # 后端 + 前端
#   .\scripts\start-local.ps1 backend    # 只启动后端
#   .\scripts\start-local.ps1 frontend   # 只启动前端（next dev，带 HMR）
#   .\scripts\start-local.ps1 frontend -Prod  # 只启动前端（生产构建，先 npm run build）
# 停止服务： .\scripts\stop-local.ps1
# 指定解释器： $env:PYTHON_BIN="D:\path\to\python.exe"; .\scripts\start-local.ps1
param([string]$Mode = "all", [switch]$Prod)

# 防御：若 param 因编码问题未生效，$Mode 可能为空
if ([string]::IsNullOrWhiteSpace($Mode)) { $Mode = "all" }

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$Root = Split-Path -Parent $PSScriptRoot

# 日志统一放 logs/ 目录，不存在则创建
$LogDir = Join-Path $Root "logs"
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

# ---- 1. 选择解释器：PYTHON_BIN > backend\.venv > jobagent 托管环境 > PATH 中的 python ----
function Get-PythonPath {
    if ($env:PYTHON_BIN) { return $env:PYTHON_BIN }
    $candidates = @(
        (Join-Path $Root "backend\.venv\Scripts\python.exe"),
        (Join-Path $env:USERPROFILE ".workbuddy\binaries\python\envs\jobagent\Scripts\python.exe"),
        (Get-Command python -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1)
    )
    foreach ($c in $candidates) {
        if ($c -and (Test-Path $c)) { return $c }
    }
    throw "python.exe not found. Please set PYTHON_BIN."
}

# ---- 2. 启动分离进程 ----
# 注意：不能用 Start-Process —— 当环境里存在大小写重复的变量
# （如 HTTPS_PROXY / https_proxy）时它会抛 ArgumentException。
# 改用 .NET Process + cmd.exe 重定向，输出落文件且不会有管道死锁。
function Start-Detached {
    param([string]$WorkDir, [string]$CommandLine, [string]$LogFile)
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "cmd.exe"
    $psi.Arguments = '/c ' + $CommandLine + ' > "' + $LogFile + '" 2>&1'
    $psi.WorkingDirectory = $WorkDir
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $null = [System.Diagnostics.Process]::Start($psi)
}

# ---- 3. 端口是否已占用 ----
function Test-Port($port) {
    $c = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    return ($null -ne $c)
}

# ---- 4. 等待 HTTP 就绪 ----
function Wait-Ready($url, $timeoutSec) {
    $deadline = (Get-Date).AddSeconds($timeoutSec)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 700
        try {
            $null = Invoke-WebRequest -Uri $url -TimeoutSec 2 -UseBasicParsing
            return $true
        } catch { }
    }
    return $false
}

function Start-Backend {
    if (Test-Port 8000) {
        Write-Host "端口 8000 已被占用，跳过后端启动（如需重启先跑 .\scripts\stop-local.ps1）" -ForegroundColor Yellow
        return
    }
    $py = Get-PythonPath
    Write-Host "后端解释器: $py" -ForegroundColor Cyan
    & $py -c "import fastapi, langgraph, sqlalchemy" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[X] 该解释器缺少后端依赖" -ForegroundColor Red
        Write-Host "    安装: cd backend; & '$py' -m pip install -e ." -ForegroundColor Yellow
        return
    }

    # 不预删除日志：cmd 的 > 重定向会自动截断
    $log = Join-Path $LogDir "backend.log"
    $cmd = 'set "PYTHONPATH=." && "' + $py + '" -m uvicorn app.main:app --host 127.0.0.1 --port 8000'
    Start-Detached -WorkDir (Join-Path $Root "backend") -CommandLine $cmd -LogFile $log

    Write-Host "后端启动中... (日志: logs\backend.log)" -ForegroundColor Yellow
    if (Wait-Ready "http://127.0.0.1:8000/healthz" 40) {
        Write-Host "后端就绪    -> http://127.0.0.1:8000" -ForegroundColor Green
        Write-Host "接口文档    -> http://127.0.0.1:8000/api/docs" -ForegroundColor Green
    } else {
        Write-Host "[X] 后端 30s 内未就绪，请查看 logs\backend.log" -ForegroundColor Red
    }
}

function Start-Frontend {
    if (Test-Port 3000) {
        Write-Host "端口 3000 已被占用，跳过前端启动" -ForegroundColor Yellow
        return
    }
    $feRoot = Join-Path $Root "frontend"
    if (-not (Test-Path (Join-Path $feRoot "node_modules"))) {
        Write-Host "首次运行，安装前端依赖（约 1-2 分钟）..." -ForegroundColor Yellow
        Push-Location $feRoot
        npm install
        Pop-Location
    }

    # -Prod 走生产构建；默认走 next dev（带 HMR）。
    # 注意：部分受管/沙箱环境会拦截 next dev 对 .next 的清理，导致 dev 卡在启动阶段，
    #       此时用 -Prod（先 cd frontend; npm run build）即可正常起服务。
    if ($Prod) {
        if (-not (Test-Path (Join-Path $feRoot ".next\BUILD_ID"))) {
            Write-Host "未找到生产构建，先执行 npm run build ..." -ForegroundColor Yellow
            Push-Location $feRoot
            npm run build
            Pop-Location
        }
        $feCmd = "npm run start"
    } else {
        $feCmd = "npm run dev"
    }

    # 不预删除日志：cmd 的 > 重定向会自动截断
    $log = Join-Path $LogDir "frontend.log"
    Start-Detached -WorkDir $feRoot -CommandLine $feCmd -LogFile $log

    Write-Host "前端启动中... ($feCmd, 日志: logs\frontend.log)" -ForegroundColor Yellow

    if (Wait-Ready "http://127.0.0.1:3000" 60) {
        Write-Host "前端就绪    -> http://localhost:3000" -ForegroundColor Green
    } elseif ($Prod) {
        Write-Host "[X] 前端 60s 内未就绪，请查看 logs\frontend.log" -ForegroundColor Red
    } else {
        Write-Host "[X] next dev 未在 60s 内就绪（首次编译慢可再等等）。" -ForegroundColor Red
        Write-Host "    若日志停在 npm 横幅不再输出，说明该环境拦截了 dev 模式的 .next 清理：" -ForegroundColor DarkGray
        Write-Host "      cd frontend; npm run build" -ForegroundColor DarkGray
        Write-Host "      .\scripts\start-local.ps1 frontend -Prod" -ForegroundColor DarkGray
    }
}

switch ($Mode) {
    "backend"  { Start-Backend }
    "frontend" { Start-Frontend }
    default    { Start-Backend; Start-Frontend }
}

Write-Host ""
Write-Host "服务已作为独立进程启动，关闭本窗口不会停止它们。" -ForegroundColor DarkGray
Write-Host "查看日志: Get-Content logs\backend.log -Wait    /    Get-Content logs\frontend.log -Wait" -ForegroundColor DarkGray
Write-Host "停止服务: .\scripts\stop-local.ps1" -ForegroundColor DarkGray
