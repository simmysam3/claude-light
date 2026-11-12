// claude-light: the ball and the menu bar item. A renderer of display.json; every decision lives in
// Python (lightd.py decides what shows, lightctl.py writes the settings).
//
//   ball <display.json> <bong.wav>                                    run (supervised by lightd)
//   ball --render <color> <headline> <detail> <message> <out.png> <side>   draw one lamp to a PNG
import AppKit

struct Settings {
    var enabled = true, sound = true, grace = 120, size = 5, showMessage = false
}

struct Display {
    var visible = false, color = "yellow", headline = "", detail = "", message = ""
    var keys: [String] = [], alertId = 0, sound = true, size = 5, tray = "", status = ""
    var settings = Settings()

    static func load(_ path: String) -> Display? {
        guard let data = FileManager.default.contents(atPath: path),
              let o = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return nil }
        var d = Display()
        d.visible = o["visible"] as? Bool ?? false
        d.color = o["color"] as? String ?? "yellow"
        d.headline = o["headline"] as? String ?? ""
        d.detail = o["detail"] as? String ?? ""
        d.message = o["message"] as? String ?? ""
        d.keys = o["keys"] as? [String] ?? []
        d.alertId = o["alert_id"] as? Int ?? 0
        d.sound = o["sound"] as? Bool ?? true
        d.size = o["size"] as? Int ?? 5
        d.tray = o["tray"] as? String ?? ""
        d.status = o["status"] as? String ?? ""
        if let c = o["config"] as? [String: Any] {
            d.settings.enabled = c["enabled"] as? Bool ?? true
            d.settings.sound = c["sound"] as? Bool ?? true
            d.settings.grace = c["grace_seconds"] as? Int ?? 120
            d.settings.size = c["size"] as? Int ?? 5
            d.settings.showMessage = c["show_message"] as? Bool ?? false
        }
        return d
    }
}

func lampColor(_ name: String) -> NSColor? {
    switch name {
    case "green":  return NSColor(srgbRed: 0.10, green: 0.90, blue: 0.38, alpha: 1)
    case "yellow": return NSColor(srgbRed: 1.00, green: 0.76, blue: 0.08, alpha: 1)
    case "red":    return NSColor(srgbRed: 1.00, green: 0.16, blue: 0.14, alpha: 1)
    default:       return nil
    }
}

final class LampPanel: NSPanel {
    override var canBecomeKey: Bool { false }
    override var canBecomeMain: Bool { false }
}

final class LampView: NSView {
    var display = Display() { didSet { needsDisplay = true } }
    var onClick: (() -> Void)?

    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
    override func mouseDown(with event: NSEvent) { onClick?() }

    override func draw(_ dirtyRect: NSRect) {
        let c = lampColor(display.color) ?? lampColor("yellow")!
        let center = NSPoint(x: bounds.midX, y: bounds.midY)
        let r = min(bounds.width, bounds.height) / 2 / 1.12   // room for the halo

        NSGradient(colors: [c.withAlphaComponent(0.55), c.withAlphaComponent(0.0)])!
            .draw(fromCenter: center, radius: r * 0.95, toCenter: center, radius: r * 1.12, options: [])
        let ring = NSBezierPath(ovalIn: NSRect(x: center.x - r, y: center.y - r, width: 2 * r, height: 2 * r))
        NSGradient(starting: NSColor(white: 0.24, alpha: 1), ending: NSColor(white: 0.04, alpha: 1))!
            .draw(in: ring, angle: -90)
        let lr = r * 0.86
        let lens = NSBezierPath(ovalIn: NSRect(x: center.x - lr, y: center.y - lr, width: 2 * lr, height: 2 * lr))
        let hot = c.blended(withFraction: 0.55, of: .white) ?? c
        let rim = c.blended(withFraction: 0.55, of: .black) ?? c
        NSGradient(colors: [hot, c, rim], atLocations: [0.0, 0.55, 1.0], colorSpace: .sRGB)!
            .draw(in: lens, relativeCenterPosition: NSPoint(x: 0, y: 0.18))
        let hl = NSBezierPath(ovalIn: NSRect(x: center.x - lr * 0.62, y: center.y + lr * 0.28,
                                             width: lr * 1.24, height: lr * 0.58))
        NSGradient(starting: NSColor(white: 1, alpha: 0.42), ending: NSColor(white: 1, alpha: 0.0))!
            .draw(in: hl, angle: -90)

        let red = display.color == "red"
        let ink = red ? NSColor.white : NSColor(white: 0.07, alpha: 0.92)
        let shadow = NSShadow()
        shadow.shadowColor = red ? NSColor(white: 0, alpha: 0.55) : NSColor(white: 1, alpha: 0.35)
        shadow.shadowOffset = NSSize(width: 0, height: -1)
        shadow.shadowBlurRadius = 3
        let width = lr * 1.5
        if !display.message.isEmpty {
            text(display.headline, size: lr * 0.12, weight: .heavy, ink: ink, shadow: shadow,
                 box: NSRect(x: center.x - width / 2, y: center.y + lr * 0.30, width: width, height: lr * 0.22))
            text(display.detail, size: lr * 0.07, weight: .semibold, ink: ink, shadow: shadow,
                 box: NSRect(x: center.x - width / 2, y: center.y + lr * 0.18, width: width, height: lr * 0.12))
            let mw = lr * 1.42
            text(display.message, size: lr * 0.068, weight: .medium, ink: ink, shadow: shadow,
                 box: NSRect(x: center.x - mw / 2, y: center.y - lr * 0.66, width: mw, height: lr * 0.80),
                 dropFromStart: true)
        } else {
            text(display.headline, size: lr * 0.15, weight: .heavy, ink: ink, shadow: shadow,
                 box: NSRect(x: center.x - width / 2, y: center.y - lr * 0.10, width: width, height: lr * 0.26))
            text(display.detail, size: lr * 0.085, weight: .semibold, ink: ink, shadow: shadow,
                 box: NSRect(x: center.x - width / 2, y: center.y - lr * 0.40, width: width, height: lr * 0.26))
        }
        text("click to dismiss", size: lr * 0.05, weight: .regular, ink: ink.withAlphaComponent(0.6),
             shadow: shadow, box: NSRect(x: center.x - width / 2, y: center.y - lr * 0.80, width: width, height: lr * 0.08))
    }

    /// Draw text centred in box; if it overflows, drop words from the start (the ask is at the end).
    private func text(_ s: String, size: CGFloat, weight: NSFont.Weight, ink: NSColor, shadow: NSShadow,
                      box: NSRect, dropFromStart: Bool = false) {
        guard !s.isEmpty, size > 1 else { return }
        let para = NSMutableParagraphStyle()
        para.alignment = .center
        para.lineBreakMode = .byWordWrapping
        let attrs: [NSAttributedString.Key: Any] = [
            .font: NSFont.systemFont(ofSize: size, weight: weight),
            .foregroundColor: ink, .shadow: shadow, .paragraphStyle: para,
        ]
        func measure(_ t: String) -> CGFloat {
            NSAttributedString(string: t, attributes: attrs)
                .boundingRect(with: NSSize(width: box.width, height: .greatestFiniteMagnitude),
                              options: [.usesLineFragmentOrigin, .usesFontLeading]).height
        }
        var str = s
        if dropFromStart {
            var words = s.split(separator: " ").map(String.init)
            while words.count > 1 && measure(str) > box.height {
                words.removeFirst()
                str = "…" + words.joined(separator: " ")
            }
        }
        let h = min(measure(str), box.height)
        NSAttributedString(string: str, attributes: attrs)
            .draw(with: NSRect(x: box.minX, y: box.midY - h / 2, width: box.width, height: h),
                  options: [.usesLineFragmentOrigin, .usesFontLeading, .truncatesLastVisibleLine])
    }
}

final class Ball: NSObject, NSApplicationDelegate, NSMenuDelegate {
    let root: String, displayPath: String, bongPath: String
    let panel: LampPanel
    let view = LampView()
    var item: NSStatusItem?
    var current = Display()
    var dismissed = Set<String>()
    var lastBonged = -1
    var preview: (display: Display, until: Date)?
    var shownSize = 0

    init(displayPath: String, bongPath: String) {
        self.displayPath = displayPath
        self.bongPath = bongPath
        root = (displayPath as NSString).deletingLastPathComponent
        panel = LampPanel(contentRect: .zero, styleMask: [.borderless, .nonactivatingPanel],
                          backing: .buffered, defer: false)
        super.init()
        panel.level = .screenSaver
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary, .ignoresCycle]
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = false
        panel.hidesOnDeactivate = false
        panel.isMovable = false
        panel.contentView = view
        view.onClick = { [weak self] in self?.dismiss() }
    }

    func applicationDidFinishLaunching(_ n: Notification) {
        let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        let menu = NSMenu()
        menu.delegate = self
        item.menu = menu
        item.button?.toolTip = "claude-light"
        self.item = item
        Timer.scheduledTimer(withTimeInterval: 0.25, repeats: true) { [weak self] _ in self?.poll() }
        poll()
    }

    // MARK: display

    func poll() {
        if let color = takePreviewRequest() { startPreview(color) }
        if let p = preview, p.until > Date() {
            render(p.display)
            updateTray()
            return
        }
        if preview != nil { preview = nil; panel.orderOut(nil) }
        guard let d = Display.load(displayPath) else { return }
        current = d
        let suppressed = !d.keys.isEmpty && Set(d.keys).isSubset(of: dismissed)
        if d.visible && !suppressed { render(d) } else { panel.orderOut(nil) }
        if !d.visible { dismissed.removeAll() }
        updateTray()
    }

    func render(_ d: Display) {
        view.display = d
        if !panel.isVisible || shownSize != d.size {
            panel.setFrame(ballFrame(size: d.size), display: true)
            shownSize = d.size
        }
        if !panel.isVisible { panel.orderFrontRegardless() }
        if d.alertId != lastBonged {
            lastBonged = d.alertId
            if d.sound { bong(d.alertId) } else { log("alert=\(d.alertId) shown silently (sound off)") }
        }
    }

    /// Size n of 10: the ball's diameter is n/10 of the screen's usable height, pinned top-right.
    func ballFrame(size: Int) -> NSRect {
        guard let screen = NSScreen.screens.first else { return .zero }
        let v = screen.visibleFrame
        let full = min(v.width, v.height)
        let side = full * CGFloat(max(1, min(10, size))) / 10
        let margin = max(0, min(v.height * 0.012, (full - side) / 2))
        return NSRect(x: v.maxX - side - margin, y: v.maxY - side - margin, width: side, height: side)
    }

    func bong(_ alert: Int) {
        for delay in [0.0, 1.1] {
            DispatchQueue.main.asyncAfter(deadline: .now() + delay) { [bongPath] in
                let file = NSSound(contentsOfFile: bongPath, byReference: true)
                let played = (file ?? NSSound(named: "Submarine"))?.play() ?? false
                self.log("bong alert=\(alert) file=\(file != nil) played=\(played)")
            }
        }
    }

    func dismiss() {
        panel.orderOut(nil)
        if preview != nil { preview = nil; return }
        dismissed.formUnion(current.keys)
        let ack = root + "/ack.json"
        if let data = try? JSONSerialization.data(withJSONObject: ["keys": current.keys]) {
            let tmp = ack + ".tmp"
            FileManager.default.createFile(atPath: tmp, contents: data)
            _ = try? FileManager.default.replaceItemAt(URL(fileURLWithPath: ack), withItemAt: URL(fileURLWithPath: tmp))
            if !FileManager.default.fileExists(atPath: ack) { try? FileManager.default.moveItem(atPath: tmp, toPath: ack) }
        }
    }

    // MARK: preview (menu, or `claude-light preview <color>` writing preview.json)

    func takePreviewRequest() -> String? {
        let path = root + "/preview.json"
        guard let data = FileManager.default.contents(atPath: path) else { return nil }
        try? FileManager.default.removeItem(atPath: path)
        let o = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
        return o?["color"] as? String ?? "yellow"
    }

    func startPreview(_ color: String) {
        var d = Display()
        d.visible = true
        d.color = lampColor(color) == nil ? "yellow" : color
        d.headline = ["green": "QUESTION FOR YOU", "yellow": "WAITING FOR YOU", "red": "ERROR"][d.color] ?? "PREVIEW"
        d.detail = "preview"
        d.message = current.settings.showMessage
            ? "This is where the end of Claude's last message appears, so you can see what it is asking for."
            : ""
        d.sound = current.settings.sound
        d.size = current.settings.size
        d.alertId = -1 - Int(Date().timeIntervalSince1970 * 10) % 1_000_000   // a fresh bong each time
        panel.orderOut(nil)
        preview = (d, Date().addingTimeInterval(6))
    }

    // MARK: menu bar

    func updateTray() {
        guard let button = item?.button else { return }
        let enabled = current.settings.enabled
        let color = enabled ? (preview?.display.color ?? current.tray) : ""
        button.image = NSImage(size: NSSize(width: 18, height: 18), flipped: false) { rect in
            let dot = NSBezierPath(ovalIn: rect.insetBy(dx: 3.5, dy: 3.5))
            if let c = lampColor(color) {
                c.setFill(); dot.fill()
                NSColor(white: 0, alpha: 0.35).setStroke(); dot.lineWidth = 1; dot.stroke()
            } else {
                NSColor.labelColor.withAlphaComponent(enabled ? 0.85 : 0.35).setStroke()
                dot.lineWidth = 1.5; dot.stroke()
                if !enabled {
                    let slash = NSBezierPath()
                    slash.move(to: NSPoint(x: rect.minX + 3, y: rect.minY + 3))
                    slash.line(to: NSPoint(x: rect.maxX - 3, y: rect.maxY - 3))
                    slash.lineWidth = 1.5; slash.stroke()
                }
            }
            return true
        }
    }

    func menuNeedsUpdate(_ menu: NSMenu) {
        menu.removeAllItems()
        let s = current.settings
        menu.addItem(withTitle: statusLine(), action: nil, keyEquivalent: "")
        menu.addItem(.separator())
        toggle(menu, "Light on", ["on"], ["off"], s.enabled)
        toggle(menu, "Sound", ["sound", "on"], ["sound", "off"], s.sound)
        toggle(menu, "Show Claude's message", ["message", "on"], ["message", "off"], s.showMessage)

        let delay = NSMenuItem(title: "Delay before the ball", action: nil, keyEquivalent: "")
        let dm = NSMenu()
        for (label, secs) in [("Immediately", 0), ("30 seconds", 30), ("1 minute", 60), ("2 minutes", 120),
                              ("5 minutes", 300), ("10 minutes", 600)] {
            radio(dm, label, ["delay", String(secs)], s.grace == secs)
        }
        delay.submenu = dm
        menu.addItem(delay)

        let size = NSMenuItem(title: "Size", action: nil, keyEquivalent: "")
        let sm = NSMenu()
        for n in 1...10 { radio(sm, "\(n * 10)% of the screen", ["size", String(n)], s.size == n) }
        size.submenu = sm
        menu.addItem(size)

        menu.addItem(.separator())
        let pv = NSMenuItem(title: "Preview", action: nil, keyEquivalent: "")
        let pm = NSMenu()
        for color in ["green", "yellow", "red"] {
            let i = NSMenuItem(title: color.capitalized, action: #selector(previewItem(_:)), keyEquivalent: "")
            i.target = self
            i.representedObject = color
            pm.addItem(i)
        }
        pv.submenu = pm
        menu.addItem(pv)
        if panel.isVisible {
            let d = NSMenuItem(title: "Dismiss the ball", action: #selector(dismissItem), keyEquivalent: "")
            d.target = self
            menu.addItem(d)
        }
        let help = NSMenuItem(title: "Help…", action: #selector(openReadme), keyEquivalent: "")
        help.target = self
        menu.addItem(help)
    }

    func statusLine() -> String {
        current.status.isEmpty ? "claude-light" : current.status   // written by lightd (lightcore.status_line)
    }

    func toggle(_ menu: NSMenu, _ title: String, _ onArgs: [String], _ offArgs: [String], _ isOn: Bool) {
        let i = NSMenuItem(title: title, action: #selector(ctlItem(_:)), keyEquivalent: "")
        i.target = self
        i.state = isOn ? .on : .off
        i.representedObject = isOn ? offArgs : onArgs
        menu.addItem(i)
    }

    func radio(_ menu: NSMenu, _ title: String, _ args: [String], _ isOn: Bool) {
        let i = NSMenuItem(title: title, action: #selector(ctlItem(_:)), keyEquivalent: "")
        i.target = self
        i.state = isOn ? .on : .off
        i.representedObject = args
        menu.addItem(i)
    }

    @objc func ctlItem(_ sender: NSMenuItem) {
        guard let args = sender.representedObject as? [String] else { return }
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
        p.arguments = [root + "/src/lightctl.py"] + args
        p.standardOutput = FileHandle.nullDevice
        do { try p.run() } catch { log("menu: could not run lightctl.py: \(error)") }
    }

    @objc func previewItem(_ sender: NSMenuItem) { startPreview(sender.representedObject as? String ?? "yellow") }
    @objc func dismissItem() { dismiss() }
    @objc func openReadme() { NSWorkspace.shared.open(URL(fileURLWithPath: root + "/README.md")) }

    func log(_ s: String) { FileHandle.standardError.write("ball: \(s)\n".data(using: .utf8)!) }
}

let args = CommandLine.arguments
if args.count >= 8 && args[1] == "--render" {
    let side = CGFloat(Double(args[7]) ?? 800)
    let v = LampView(frame: NSRect(x: 0, y: 0, width: side, height: side))
    var d = Display()
    d.color = args[2]; d.headline = args[3]; d.detail = args[4]; d.message = args[5]
    v.display = d
    let rep = v.bitmapImageRepForCachingDisplay(in: v.bounds)!
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
    NSColor(srgbRed: 0.24, green: 0.29, blue: 0.35, alpha: 1).setFill()
    v.bounds.fill()
    v.draw(v.bounds)
    NSGraphicsContext.restoreGraphicsState()
    try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: args[6]))
    exit(0)
}
guard args.count >= 3 else {
    FileHandle.standardError.write("usage: ball <display.json> <bong.wav>\n".data(using: .utf8)!)
    exit(2)
}
let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let ball = Ball(displayPath: args[1], bongPath: args[2])
app.delegate = ball
app.run()
