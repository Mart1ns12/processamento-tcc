# Dia completo (rotina -> carga completa -> publicador) chamado pelo Agendador de Tarefas do Windows.
# Usa --esperar: a rotina espera a coleta nos prazos de parametros.yaml (rotina.prazo 09:45 = limite
# para contar no historico; rotina.prazo_tardio 12:00 = rodada tardia). Sem -Data, usa hoje.
# Log: logs\agendador-AAAA-MM-DD.log (a rotina continua gravando o dela em logs\rotina-AAAA-MM-DD.log).
# Codigo de saida = o do processamento.painel.dia (0 publicado; 3 sem saida nova, ex.: dia sem pregao).

param(
    [string]$Data = (Get-Date -Format 'yyyy-MM-dd')
)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Join-Path $PSScriptRoot '..')

if ($Data -notmatch '^\d{4}-\d{2}-\d{2}$') {
    Write-Error "Data invalida: '$Data' (use AAAA-MM-DD)."
    exit 2
}

New-Item -ItemType Directory -Force -Path 'logs' | Out-Null
$log = Join-Path 'logs' "agendador-$Data.log"

$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUNBUFFERED = '1'

"=== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') inicio: dia $Data (--esperar) ===" |
    Out-File -FilePath $log -Append -Encoding utf8

# O cmd grava direto no arquivo (utf-8 do Python, stdout + stderr): passar pelo pipe do PowerShell 5.1
# estragaria os acentos e transformaria stderr em erro.
$ErrorActionPreference = 'Continue'
cmd /c ".\.venv\Scripts\python.exe -m processamento.painel.dia --data $Data --esperar >> `"$log`" 2>&1"
$codigo = $LASTEXITCODE

"=== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') fim: codigo $codigo ===" |
    Out-File -FilePath $log -Append -Encoding utf8
exit $codigo
