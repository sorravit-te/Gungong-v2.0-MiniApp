param(
    [Parameter(Mandatory = $true)][string]$SeccompProfile,
    [string]$ContainerName = 'gungong-renderer-local-test'
)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$profilePath = (Resolve-Path -LiteralPath $SeccompProfile).Path
if ($ContainerName -notmatch '^gungong-renderer-local[-a-z0-9]*$') {
    throw 'Use a task-specific renderer container name'
}
if ((docker ps -a --format '{{.Names}}') -contains $ContainerName) {
    throw 'Container already exists; inspect it before replacing it'
}
# Dedicated ephemeral worker authentication, NOT any API/Firestore credential.
$tokenBytes = New-Object byte[] 32
[System.Security.Cryptography.RandomNumberGenerator]::Fill($tokenBytes)
$env:URL_RENDER_WORKER_TOKEN = [Convert]::ToHexString($tokenBytes)
$env:URL_RENDER_WORKER_URL = 'http://127.0.0.1:8071'
docker build -f (Join-Path $PSScriptRoot 'Dockerfile') -t gungong-renderer-local-test $projectRoot
if ($LASTEXITCODE -ne 0) { throw 'Renderer build failed' }
docker run -d --name $ContainerName --init --read-only --user 10001:10001 `
    --cap-drop ALL --security-opt no-new-privileges --security-opt "seccomp=$profilePath" `
    --memory 768m --memory-swap 768m --cpus 1 --pids-limit 128 --shm-size 128m `
    --tmpfs '/tmp:rw,noexec,nosuid,size=128m,mode=1777' --network bridge `
    -p 127.0.0.1:8071:8071 -e URL_RENDER_WORKER_TOKEN gungong-renderer-local-test
if ($LASTEXITCODE -ne 0) { throw 'Renderer start failed' }
Write-Output 'Local renderer started on 127.0.0.1:8071. Token stays in this shell; not printed.'
Write-Output 'API opt-in still required; do not deploy this local configuration.'
