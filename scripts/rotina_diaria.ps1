# Rotina diaria do TCC (etapa 8). Chamada pelo Agendador de Tarefas do Windows.
# O log e gravado pelo proprio Python em logs\rotina-AAAA-MM-DD.log (sem redirecionamento).
# Codigos de saida: ver LEIA-ME.md, secao "Rotina diaria no Agendador de Tarefas".

Set-Location -LiteralPath "$PSScriptRoot\.."
& .\.venv\Scripts\python.exe -m processamento.rotina
exit $LASTEXITCODE
