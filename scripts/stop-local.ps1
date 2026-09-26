# 停止 JobAgent v2 本地服务（按端口杀进程）
param([int[]]$Ports = @(8000, 3000))

foreach ($port in $Ports) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) {
        Write-Host "端口 $port 无监听进程" -ForegroundColor DarkGray
        continue
    }
    foreach ($c in $conns) {
        $proc = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "停止端口 $port -> $($proc.ProcessName) (PID $($proc.Id))" -ForegroundColor Yellow
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
Write-Host "已停止。" -ForegroundColor Green
