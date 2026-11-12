# claude-light ball for Windows: the lamp (a WPF window that floats above everything and never takes
# focus) and the tray icon with every setting. A renderer of display.json; every decision lives in
# ..\src (lightd.py decides what shows, lightctl.py writes the settings).
#
#   powershell -NoProfile -ExecutionPolicy Bypass -STA -File ball.ps1 <display.json> <bong.wav> <pythonw.exe>
param([string]$DisplayPath, [string]$BongPath, [string]$Python)

Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase, System.Windows.Forms, System.Drawing
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class ClaudeLightWin32 {
    [DllImport("user32.dll")] public static extern int GetWindowLong(IntPtr hWnd, int nIndex);
    [DllImport("user32.dll")] public static extern int SetWindowLong(IntPtr hWnd, int nIndex, int dwNewLong);
    [DllImport("user32.dll")] public static extern bool DestroyIcon(IntPtr hIcon);
}
"@

$Root = Split-Path -Parent $DisplayPath
$LogPath = Join-Path $Root 'ball.log'
function Log([string]$s) { try { Add-Content -LiteralPath $LogPath -Value ("{0:s} ball: {1}" -f (Get-Date), $s) } catch {} }

$Hex = @{ green = '1AE661'; yellow = 'FFC214'; red = 'FF2924' }
$Headlines = @{ green = 'QUESTION FOR YOU'; yellow = 'WAITING FOR YOU'; red = 'ERROR' }

# ---- the window: a 1000x1000 design scaled by a Viewbox (same proportions as the Mac lamp) ----------
[xml]$xaml = @"
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        WindowStyle="None" AllowsTransparency="True" Background="Transparent" Topmost="True"
        ShowInTaskbar="False" ShowActivated="False" ResizeMode="NoResize" Width="500" Height="500">
  <Viewbox Stretch="Uniform">
    <Grid Width="1000" Height="1000">
      <Ellipse x:Name="Halo" Width="1000" Height="1000"/>
      <Ellipse x:Name="Ring" Width="893" Height="893"/>
      <Ellipse x:Name="Lens" Width="768" Height="768"/>
      <Ellipse x:Name="Shine" Width="476" Height="223" VerticalAlignment="Top" Margin="0,170,0,0"/>
      <StackPanel VerticalAlignment="Center" HorizontalAlignment="Center" Width="576">
        <TextBlock x:Name="Headline" FontSize="58" FontWeight="Black" TextAlignment="Center" TextWrapping="Wrap"/>
        <TextBlock x:Name="Detail" FontSize="33" FontWeight="SemiBold" TextAlignment="Center" TextWrapping="Wrap" Margin="0,12,0,0"/>
        <TextBlock x:Name="Message" FontSize="26" FontWeight="Medium" TextAlignment="Center" TextWrapping="Wrap" Margin="0,24,0,0" MaxHeight="300"/>
      </StackPanel>
      <TextBlock x:Name="Hint" Text="click to dismiss" FontSize="19" VerticalAlignment="Bottom" HorizontalAlignment="Center" Margin="0,0,0,190"/>
    </Grid>
  </Viewbox>
</Window>
"@
$win = [Windows.Markup.XamlReader]::Load((New-Object System.Xml.XmlNodeReader $xaml))
$Halo = $win.FindName('Halo'); $Ring = $win.FindName('Ring'); $Lens = $win.FindName('Lens'); $Shine = $win.FindName('Shine')
$Headline = $win.FindName('Headline'); $Detail = $win.FindName('Detail'); $Message = $win.FindName('Message'); $Hint = $win.FindName('Hint')

$win.Add_SourceInitialized({
    $h = (New-Object System.Windows.Interop.WindowInteropHelper $win).Handle
    $ex = [ClaudeLightWin32]::GetWindowLong($h, -20)                        # GWL_EXSTYLE
    [void][ClaudeLightWin32]::SetWindowLong($h, -20, ($ex -bor 0x08000000 -bor 0x80))   # NOACTIVATE | TOOLWINDOW
})
$win.Add_MouseLeftButtonDown({ Dismiss })

function MediaColor([string]$hex, [byte]$alpha = 255) {
    $c = [Windows.Media.ColorConverter]::ConvertFromString('#' + $hex)
    return [Windows.Media.Color]::FromArgb($alpha, $c.R, $c.G, $c.B)
}
function Blend([Windows.Media.Color]$a, [Windows.Media.Color]$b, [double]$f) {
    return [Windows.Media.Color]::FromArgb(255, [byte]($a.R + ($b.R - $a.R) * $f), [byte]($a.G + ($b.G - $a.G) * $f), [byte]($a.B + ($b.B - $a.B) * $f))
}
function GStop([Windows.Media.Color]$c, [double]$at) { return New-Object Windows.Media.GradientStop $c, $at }

$Ring.Fill = New-Object Windows.Media.LinearGradientBrush ([Windows.Media.Color]::FromRgb(61, 61, 61)), ([Windows.Media.Color]::FromRgb(10, 10, 10)), 90
$shineBrush = New-Object Windows.Media.LinearGradientBrush ([Windows.Media.Color]::FromArgb(107, 255, 255, 255)), ([Windows.Media.Color]::FromArgb(0, 255, 255, 255)), 90
$Shine.Fill = $shineBrush

$script:painted = ''
function Paint([string]$name) {
    if (-not $Hex.ContainsKey($name)) { $name = 'yellow' }
    if ($script:painted -eq $name) { return }          # brushes only change with the colour
    $script:painted = $name
    $c = MediaColor $Hex[$name]
    $halo = New-Object Windows.Media.RadialGradientBrush
    $halo.GradientStops.Add((GStop (MediaColor $Hex[$name] 140) 0.0))
    $halo.GradientStops.Add((GStop (MediaColor $Hex[$name] 140) 0.85))
    $halo.GradientStops.Add((GStop (MediaColor $Hex[$name] 0) 1.0))
    $Halo.Fill = $halo
    $lens = New-Object Windows.Media.RadialGradientBrush
    $lens.GradientOrigin = New-Object Windows.Point 0.5, 0.41
    $lens.Center = New-Object Windows.Point 0.5, 0.41
    $lens.RadiusX = 0.6; $lens.RadiusY = 0.6
    $lens.GradientStops.Add((GStop (Blend $c ([Windows.Media.Colors]::White) 0.55) 0.0))
    $lens.GradientStops.Add((GStop $c 0.55))
    $lens.GradientStops.Add((GStop (Blend $c ([Windows.Media.Colors]::Black) 0.55) 1.0))
    $Lens.Fill = $lens
    if ($name -eq 'red') { $ink = [Windows.Media.Colors]::White } else { $ink = [Windows.Media.Color]::FromArgb(235, 18, 18, 18) }
    $brush = New-Object Windows.Media.SolidColorBrush $ink
    $faint = New-Object Windows.Media.SolidColorBrush ([Windows.Media.Color]::FromArgb(150, $ink.R, $ink.G, $ink.B))
    $Headline.Foreground = $brush; $Detail.Foreground = $brush; $Message.Foreground = $brush; $Hint.Foreground = $faint
}

function Place([int]$size) {
    $wa = [System.Windows.SystemParameters]::WorkArea
    $full = [Math]::Min($wa.Width, $wa.Height)
    $side = $full * [Math]::Max(1, [Math]::Min(10, $size)) / 10
    $margin = [Math]::Max(0, [Math]::Min($wa.Height * 0.012, ($full - $side) / 2))
    $win.Width = $side; $win.Height = $side
    $win.Left = $wa.Right - $side - $margin; $win.Top = $wa.Top + $margin
}

# ---- sound: two players so the second bong does not cut the first ------------------------------
$players = @((New-Object Windows.Media.MediaPlayer), (New-Object Windows.Media.MediaPlayer))
function PlayOne([int]$i) {
    try { $p = $players[$i]; $p.Open([Uri]$BongPath); $p.Position = [TimeSpan]::Zero; $p.Play(); Log "bong played=true" }
    catch { Log "bong failed: $_" }
}
$second = New-Object Windows.Threading.DispatcherTimer
$second.Interval = [TimeSpan]::FromMilliseconds(1100)
$second.Add_Tick({ $second.Stop(); PlayOne 1 })
function Bong { PlayOne 0; $second.Start() }

# ---- state --------------------------------------------------------------------------------------
$script:current = $null
$script:dismissed = New-Object 'System.Collections.Generic.HashSet[string]'
$script:lastBonged = $null
$script:preview = $null
$script:previewUntil = Get-Date
$script:shownSize = 0
$script:trayKey = ''

function ReadJson([string]$path) {
    try { if (Test-Path -LiteralPath $path) { return (Get-Content -Raw -LiteralPath $path | ConvertFrom-Json) } } catch {}
    return $null
}
function KeysOf($d) { if ($d -and $d.keys) { return @($d.keys) } else { return @() } }

function Render($d) {
    Paint ([string]$d.color)
    $Headline.Text = [string]$d.headline
    $Detail.Text = [string]$d.detail
    $Message.Text = [string]$d.message
    if ($d.message) { $Message.Visibility = 'Visible' } else { $Message.Visibility = 'Collapsed' }
    $size = 5; if ($d.size) { $size = [int]$d.size }
    if (-not $win.IsVisible -or $script:shownSize -ne $size) { Place $size; $script:shownSize = $size }
    if (-not $win.IsVisible) { $win.Show() }
    if ([string]$d.alert_id -ne [string]$script:lastBonged) {
        $script:lastBonged = $d.alert_id
        if ($d.sound -ne $false) { Bong } else { Log "alert=$($d.alert_id) shown silently (sound off)" }
    }
}

function Dismiss {
    $win.Hide()
    if ($script:preview) { $script:preview = $null; return }
    $keys = KeysOf $script:current
    foreach ($k in $keys) { [void]$script:dismissed.Add([string]$k) }
    try {
        $ack = Join-Path $Root 'ack.json'
        $json = ConvertTo-Json @{ keys = [string[]]$keys } -Compress
        Set-Content -LiteralPath "$ack.tmp" -Value $json -Encoding ASCII
        Move-Item -LiteralPath "$ack.tmp" -Destination $ack -Force
    } catch { Log "ack failed: $_" }
}

function StartPreview([string]$color) {
    if (-not $Hex.ContainsKey($color)) { $color = 'yellow' }
    $cfg = $null; if ($script:current) { $cfg = $script:current.config }
    $msg = ''
    if ($cfg -and $cfg.show_message) { $msg = "This is where the end of Claude's last message appears, so you can see what it is asking for." }
    $win.Hide()
    $script:preview = [pscustomobject]@{
        visible = $true; color = $color; headline = $Headlines[$color]; detail = 'preview'; message = $msg
        sound = (-not $cfg) -or ($cfg.sound -ne $false); size = $(if ($cfg -and $cfg.size) { [int]$cfg.size } else { 5 })
        alert_id = 'preview-' + (Get-Date).Ticks
    }
    $script:previewUntil = (Get-Date).AddSeconds(6)
}

function Poll {
    try {
        $req = Join-Path $Root 'preview.json'
        if (Test-Path -LiteralPath $req) {
            $p = ReadJson $req
            Remove-Item -LiteralPath $req -ErrorAction SilentlyContinue
            $color = 'yellow'; if ($p -and $p.color) { $color = [string]$p.color }
            StartPreview $color
        }
        if ($script:preview -and (Get-Date) -lt $script:previewUntil) { Render $script:preview; UpdateTray; return }
        if ($script:preview) { $script:preview = $null; $win.Hide() }
        $d = ReadJson $DisplayPath
        if (-not $d) { return }
        $script:current = $d
        $keys = KeysOf $d
        $suppressed = $false
        if ($keys.Count -gt 0) {
            $suppressed = $true
            foreach ($k in $keys) { if (-not $script:dismissed.Contains([string]$k)) { $suppressed = $false } }
        }
        if ($d.visible -and -not $suppressed) { Render $d } else { $win.Hide() }
        if (-not $d.visible) { $script:dismissed.Clear() }
        UpdateTray
    } catch { Log "poll failed: $_" }
}

# ---- tray icon and its menu ---------------------------------------------------------------------
$tray = New-Object System.Windows.Forms.NotifyIcon
$tray.Text = 'claude-light'
$menu = New-Object System.Windows.Forms.ContextMenuStrip
$tray.ContextMenuStrip = $menu

function DotIcon([string]$name, [bool]$enabled) {
    $bmp = New-Object System.Drawing.Bitmap 16, 16
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    if ($enabled -and $Hex.ContainsKey($name)) {
        $fill = New-Object System.Drawing.SolidBrush ([System.Drawing.ColorTranslator]::FromHtml('#' + $Hex[$name]))
        $g.FillEllipse($fill, 2, 2, 11, 11); $fill.Dispose()
    } else {
        $pen = New-Object System.Drawing.Pen ([System.Drawing.Color]::Gray), 1.6
        $g.DrawEllipse($pen, 2, 2, 11, 11)
        if (-not $enabled) { $g.DrawLine($pen, 2, 13, 13, 2) }
        $pen.Dispose()
    }
    $g.Dispose()
    $h = $bmp.GetHicon()
    $icon = [System.Drawing.Icon]::FromHandle($h).Clone()
    [void][ClaudeLightWin32]::DestroyIcon($h); $bmp.Dispose()
    return $icon
}

function UpdateTray {
    $d = $script:current
    $enabled = $true; if ($d -and $d.config) { $enabled = [bool]$d.config.enabled }
    $color = ''
    if ($script:preview) { $color = [string]$script:preview.color } elseif ($d) { $color = [string]$d.tray }
    $status = 'claude-light'; if ($d -and $d.status) { $status = [string]$d.status }
    $key = "$color|$enabled|$status"
    if ($key -eq $script:trayKey) { return }
    $script:trayKey = $key
    $old = $tray.Icon
    $tray.Icon = DotIcon $color $enabled
    if ($old) { $old.Dispose() }
    if ($status.Length -gt 63) { $status = $status.Substring(0, 62) + [char]0x2026 }   # tray tooltips stop at 63
    $tray.Text = $status
    $tray.Visible = $true
}

function Ctl([string[]]$cmd) {
    $ctlPath = Join-Path $Root 'src\lightctl.py'
    $argList = @('"' + $ctlPath + '"') + $cmd
    try { Start-Process -FilePath $Python -ArgumentList $argList -WindowStyle Hidden } catch { Log "menu: $_" }
}

function Item([string]$title, $tag, [bool]$checked) {
    $i = New-Object System.Windows.Forms.ToolStripMenuItem $title
    $i.Checked = $checked
    $i.Tag = $tag
    $i.Add_Click({ param($s, $e) Ctl ([string[]]$s.Tag) })
    return $i
}

$menu.Add_Opening({
    $menu.Items.Clear()
    $d = $script:current
    $cfg = $null; if ($d) { $cfg = $d.config }
    if (-not $cfg) { $cfg = [pscustomobject]@{ enabled = $true; sound = $true; show_message = $false; grace_seconds = 120; size = 5 } }
    $status = 'claude-light'; if ($d -and $d.status) { $status = [string]$d.status }
    $head = $menu.Items.Add($status); $head.Enabled = $false
    [void]$menu.Items.Add((New-Object System.Windows.Forms.ToolStripSeparator))
    if ($cfg.enabled) { $t = @('off') } else { $t = @('on') }
    [void]$menu.Items.Add((Item 'Light on' $t ([bool]$cfg.enabled)))
    if ($cfg.sound) { $t = @('sound', 'off') } else { $t = @('sound', 'on') }
    [void]$menu.Items.Add((Item 'Sound' $t ([bool]$cfg.sound)))
    if ($cfg.show_message) { $t = @('message', 'off') } else { $t = @('message', 'on') }
    [void]$menu.Items.Add((Item "Show Claude's message" $t ([bool]$cfg.show_message)))
    $delay = New-Object System.Windows.Forms.ToolStripMenuItem 'Delay before the ball'
    foreach ($o in @(@('Immediately', 0), @('30 seconds', 30), @('1 minute', 60), @('2 minutes', 120), @('5 minutes', 300), @('10 minutes', 600))) {
        [void]$delay.DropDownItems.Add((Item $o[0] @('delay', [string]$o[1]) ([int]$cfg.grace_seconds -eq $o[1])))
    }
    [void]$menu.Items.Add($delay)
    $size = New-Object System.Windows.Forms.ToolStripMenuItem 'Size'
    foreach ($n in 1..10) { [void]$size.DropDownItems.Add((Item "$($n * 10)% of the screen" @('size', [string]$n) ([int]$cfg.size -eq $n))) }
    [void]$menu.Items.Add($size)
    [void]$menu.Items.Add((New-Object System.Windows.Forms.ToolStripSeparator))
    $preview = New-Object System.Windows.Forms.ToolStripMenuItem 'Preview'
    foreach ($c in @('green', 'yellow', 'red')) {
        $p = New-Object System.Windows.Forms.ToolStripMenuItem ((Get-Culture).TextInfo.ToTitleCase($c))
        $p.Tag = $c
        $p.Add_Click({ param($s, $e) StartPreview ([string]$s.Tag) })
        [void]$preview.DropDownItems.Add($p)
    }
    [void]$menu.Items.Add($preview)
    if ($win.IsVisible) {
        $dm = New-Object System.Windows.Forms.ToolStripMenuItem 'Dismiss the ball'
        $dm.Add_Click({ Dismiss })
        [void]$menu.Items.Add($dm)
    }
    $help = New-Object System.Windows.Forms.ToolStripMenuItem 'Help...'
    $help.Add_Click({ try { Start-Process (Join-Path $Root 'README.md') } catch { Log "help: $_" } })
    [void]$menu.Items.Add($help)
})

# ---- run ----------------------------------------------------------------------------------------
$timer = New-Object Windows.Threading.DispatcherTimer
$timer.Interval = [TimeSpan]::FromMilliseconds(250)
$timer.Add_Tick({ Poll })
$app = New-Object System.Windows.Application
$app.ShutdownMode = [System.Windows.ShutdownMode]::OnExplicitShutdown
$app.Add_Exit({ $tray.Visible = $false; $tray.Dispose() })
Log 'started'
Poll
$timer.Start()
[void]$app.Run()
