# Kill duplicate system-Python factory workers; keep only .venv instances.
# Safe to run repeatedly (watchdog).

$ErrorActionPreference = "SilentlyContinue"
$patterns = @(
    "aggressive_loop\.py",
    "wait_and_submit\.py",
    "gate_archaludon\.py",
    "gate_dragapult\.py",
    "gate_alakazam\.py",
    "train_lucario_field_mcts\.py",
    "selfplay\.py",
    "continuous_focus_gates\.py",
    "director_dashboard\.py",
    "quota_reset_ship_monitor\.py",
    "archaludon_meta_loop\.py",
    "mainline_supervisor\.py"
)
$pat = ($patterns -join "|")

# IMPORTANT: venv\Scripts\python.exe on Windows is a launcher stub; the real
# interpreter often appears as base Python312 with PPID = venv stub.
# Only kill Python312 factory workers whose parent is NOT a .venv python.
$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'"
$byId = @{}
foreach ($p in $procs) { $byId[$p.ProcessId] = $p }
$killed = 0
foreach ($p in $procs) {
    $c = $p.CommandLine
    if (-not $c) { continue }
    if ($c -notmatch $pat) { continue }
    if ($c -notmatch 'AppData\\Local\\Programs\\Python\\Python312') { continue }
    $parent = $byId[$p.ParentProcessId]
    $pcmd = if ($parent) { $parent.CommandLine } else { "" }
    if ($pcmd -and ($pcmd -match 'PTCG_AI_Battle_Challenge\\\.venv\\Scripts\\python')) {
        # legitimate venv-launched worker — keep
        continue
    }
    try {
        Stop-Process -Id $p.ProcessId -Force
        $killed++
        Write-Output "killed orphan_syspy $($p.ProcessId) parent=$($p.ParentProcessId)"
    } catch {}
}
Write-Output "dedupe done killed=$killed utc=$([DateTime]::UtcNow.ToString('o'))"
