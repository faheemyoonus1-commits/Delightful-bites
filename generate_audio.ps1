# generate_audio.ps1  -  Delightful Bites (Unit 4) narration, word for word from the site
# Created by Faheem Yoonus V K, ALPS Cherukulathur East
#
# WHAT IT DOES
#   1. Reads the passages straight from index.html (so the audio always matches the
#      textbook text on the site), adds a little emotion to each, and asks ElevenLabs
#      to read them aloud.
#   2. Saves audio\stone-01.mp3 ... stone-09.mp3 and pancake-01.mp3 ... pancake-03.mp3
#      next to index.html. These are the exact names the site plays, so there is
#      nothing else to connect: upload index.html + the audio folder to GitHub.
#   3. Safe to run again. Clips that are finished are skipped. If your credits run out,
#      wait for them to refill (or upgrade) and run it again; it carries on from there.
#      If you change the text in index.html, that clip is made again automatically.
#
# HOW TO RUN (Windows)
#   Put this file in the SAME folder as index.html, then in PowerShell:
#     $env:ELEVENLABS_API_KEY = "paste-your-key-here"
#     powershell -ExecutionPolicy Bypass -File .\generate_audio.ps1
#   Options:  -DryRun  (show the text, spend nothing)   -Only stone-08   -Force (redo all)
#
# NEVER upload your API key to GitHub. This script reads it from the environment only.

param(
  [string]$Only = "",
  [switch]$Force,
  [switch]$DryRun,
  [string]$Html = (Join-Path $PSScriptRoot "index.html"),
  [string]$VoiceId = $(if ($env:ELEVENLABS_VOICE_ID) { $env:ELEVENLABS_VOICE_ID } else { "7wlfJf72PCt9FjPj0Beg" }),
  [string]$Model = $(if ($env:ELEVENLABS_MODEL) { $env:ELEVENLABS_MODEL } else { "eleven_v3" })
)

$ErrorActionPreference = "Stop"
$outDir = Join-Path $PSScriptRoot "audio"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
if (-not (Test-Path $Html)) { throw "Cannot find $Html . Put this script next to index.html." }

# ---- 1. read the passages from index.html -------------------------------------------
$src = Get-Content -Raw -Encoding UTF8 -Path $Html
function Get-Array([string]$name) {
  $start = $src.IndexOf("const $name = [")
  if ($start -lt 0) { throw "Could not find $name in index.html" }
  $start += ("const $name = ").Length
  $end = $src.IndexOf("`n  ];", $start)
  $json = $src.Substring($start, $end + 5 - $start).Trim()
  $json = $json.TrimEnd(';')
  # drop the big embedded pictures so Windows PowerShell can parse the rest
  $json = [regex]::Replace($json, '"(image2?)"\s*:\s*"data:[^"]*"', '"$1":""')
  return ($json | ConvertFrom-Json)
}
$stone   = Get-Array "STONE_SOUP_PASSAGES"
$pancake = Get-Array "PANCAKE_PASSAGES"

# Opening mood for each passage (my own short stage directions, not textbook text)
$stoneMood   = @("[tired, with a sigh]","[hopeful, then sad]","[playful]","[cheerful]","[eager, teasing]","[curious]","[warm, delighted]","[joyful]","[gentle, happy]")
$pancakeMood = @("[excited, then shocked]","[panicked, out of breath]","[frightened, then sly]")

function Build-Text($mood, $passage) {
  $parts = @()
  foreach ($s in $passage.sentences) {
    $t = ($s.en).Trim()
    if ($t -match '[!]["”’'']*$')      { $parts += "[excited] $t" }
    elseif ($t -match '[?]["”’'']*$')  { $parts += "[curious] $t" }
    else                               { $parts += $t }
  }
  return "$mood " + ($parts -join " ")
}

$jobs = @()
for ($i = 0; $i -lt $stone.Count; $i++) {
  $jobs += [pscustomobject]@{ Id = ("stone-{0:00}" -f $stone[$i].num); Title = $stone[$i].title; Text = (Build-Text $stoneMood[$i] $stone[$i]) }
}
for ($i = 0; $i -lt $pancake.Count; $i++) {
  $jobs += [pscustomobject]@{ Id = ("pancake-{0:00}" -f $pancake[$i].num); Title = $pancake[$i].title; Text = (Build-Text $pancakeMood[$i] $pancake[$i]) }
}
if ($Only) { $jobs = $jobs | Where-Object { $_.Id -eq $Only }; if (-not $jobs) { throw "No clip called $Only" } }

# ---- manifest: remembers which clips match the current text --------------------------
$manifestPath = Join-Path $outDir "index.json"
$manifest = @{}
if ((Test-Path $manifestPath) -and -not $Force) {
  try { (Get-Content -Raw -Encoding UTF8 $manifestPath | ConvertFrom-Json) | ForEach-Object { $manifest[$_.id] = $_ } } catch {}
}
function Get-Hash([string]$s) {
  $sha = [System.Security.Cryptography.SHA256]::Create()
  return ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($s)))).Replace("-", "")
}
function Save-Manifest {
  ($manifest.Values | Sort-Object id | ConvertTo-Json -Depth 4) | Set-Content -Encoding UTF8 $manifestPath
}

if ($DryRun) {
  foreach ($j in $jobs) { Write-Host "--- $($j.Id): $($j.Title) ($($j.Text.Length) characters)" -ForegroundColor Cyan; Write-Host $j.Text; Write-Host "" }
  $total = 0; foreach ($j in $jobs) { $total += $j.Text.Length }
  Write-Host ("Total: {0} characters (about that many ElevenLabs credits)." -f $total) -ForegroundColor Yellow
  return
}

# ---- 2. check the key and the credits ------------------------------------------------
$key = $env:ELEVENLABS_API_KEY
if (-not $key) { $key = Read-Host "Paste your ElevenLabs API key (it is not saved)" }
$headers = @{ "xi-api-key" = $key }

$remaining = $null
try {
  $sub = Invoke-RestMethod -Uri "https://api.elevenlabs.io/v1/user/subscription" -Headers $headers
  $remaining = [int]$sub.character_limit - [int]$sub.character_count
  Write-Host ("Plan: {0}. Credits left: {1}" -f $sub.tier, $remaining) -ForegroundColor Cyan
} catch {
  Write-Host "Could not read your credit balance (continuing anyway)." -ForegroundColor Yellow
}

# ---- 3. make the clips ---------------------------------------------------------------
$made = 0; $skipped = 0; $stopped = $false
foreach ($j in $jobs) {
  $file = Join-Path $outDir ("{0}.mp3" -f $j.Id)
  $hash = Get-Hash ($j.Text + "|" + $VoiceId + "|" + $Model)
  if ((Test-Path $file) -and $manifest.ContainsKey($j.Id) -and $manifest[$j.Id].hash -eq $hash) {
    Write-Host "Skip   $($j.Id) (already matches the site)" -ForegroundColor DarkGray; $skipped++; continue
  }
  if ($remaining -ne $null -and $remaining -lt $j.Text.Length) {
    Write-Host ("Not enough credits for {0} (needs about {1}, you have {2}). Wait for your credits to refill, then run this file again." -f $j.Id, $j.Text.Length, $remaining) -ForegroundColor Yellow
    $stopped = $true; break
  }
  Write-Host "Making $($j.Id): $($j.Title)" -ForegroundColor White
  $body = @{
    text = $j.Text; model_id = $Model
    voice_settings = @{ stability = 0.35; similarity_boost = 0.8; style = 0.6; use_speaker_boost = $true }
  } | ConvertTo-Json -Depth 4
  $bytes = [Text.Encoding]::UTF8.GetBytes($body)
  $uri = "https://api.elevenlabs.io/v1/text-to-speech/${VoiceId}?output_format=mp3_44100_128"
  $ok = $false
  for ($try = 1; $try -le 3 -and -not $ok; $try++) {
    try {
      Invoke-WebRequest -Uri $uri -Method Post -Headers $headers -ContentType "application/json; charset=utf-8" -Body $bytes -OutFile $file -UseBasicParsing | Out-Null
      $ok = $true
    } catch {
      $code = 0; try { $code = [int]$_.Exception.Response.StatusCode } catch {}
      $msg = ""; try { $msg = $_.ErrorDetails.Message } catch {}
      if ($code -eq 429 -and $msg -notmatch "quota") { Write-Host "  Rate limit, waiting 45 seconds..." -ForegroundColor Yellow; Start-Sleep -Seconds 45; continue }
      if ($msg -match "quota_exceeded|insufficient") { Write-Host "  Out of credits. Wait for them to refill, then run this file again." -ForegroundColor Yellow; $stopped = $true; break }
      if ($code -eq 401) { Write-Host "  The key was refused (or this voice needs a paid plan). Check the key. $msg" -ForegroundColor Red; $stopped = $true; break }
      Write-Host "  Failed ($code) $msg" -ForegroundColor Red; break
    }
  }
  if ($ok) {
    $made++
    if ($remaining -ne $null) { $remaining -= $j.Text.Length }
    $manifest[$j.Id] = [pscustomobject]@{ id = $j.Id; title = $j.Title; file = "audio/$($j.Id).mp3"; hash = $hash }
    Save-Manifest
    Write-Host ("  saved {0} ({1} KB)" -f $file, [int]((Get-Item $file).Length / 1KB)) -ForegroundColor Green
    Start-Sleep -Seconds 4
  } else {
    if (Test-Path $file) { if ((Get-Item $file).Length -lt 2000) { Remove-Item $file -Force } }
    if ($stopped) { break }
  }
}

# old retold clips from the first version are not used any more
foreach ($old in "pancake-04","pancake-05","pancake-06") { $p = Join-Path $outDir "$old.mp3"; if ((Test-Path $p) -and -not $Only) { Remove-Item $p -Force } }

Write-Host ""
Write-Host "Done: $made made, $skipped already up to date." -ForegroundColor Cyan
if ($stopped) { Write-Host "Some clips are still missing. Run the same command again later and it will carry on." -ForegroundColor Yellow }
else { Write-Host "Next: upload index.html and the audio folder to your GitHub repository." -ForegroundColor Green }
