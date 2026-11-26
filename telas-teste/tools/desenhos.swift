// SPDX-License-Identifier: GPL-3.0-or-later
// Desenha as imagens do app de teste (package/imagens):
//   <nome>.png        300×220, o desenho pequeno (peças Left_*)
//   <nome>-baixo.png  957×639, a área inteira da prévia, com o desenho no alto
//                     e o terço de baixo livre para o texto (1Graphic_1TextBottom)
//   <nome>-cima.png   957×639, com o desenho embaixo e o alto livre (1Graphic_1Text2Row/3Row)
//   regua.png         957×639, bordas, grade de 100 e as linhas de texto (56) marcadas
// 957×639 é a prévia da LT_State_Regular_ContentHidden em unidades de 1920×720
// (contentPreviewRegularW/H_ID7 da interface).
//
//   swift tools/desenhos.swift package/imagens
import AppKit

let out = CommandLine.arguments[1]
let red = NSColor(calibratedRed: 0.86, green: 0.16, blue: 0.13, alpha: 1)
let white = NSColor(calibratedWhite: 0.92, alpha: 1)
let W = 957, H = 639

func png(_ name: String, _ w: Int, _ h: Int, _ draw: (CGContext) -> Void) {
    let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: w, pixelsHigh: h, bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
    let c = NSGraphicsContext.current!.cgContext
    c.setLineCap(.round); c.setLineJoin(.round)
    draw(c)
    NSGraphicsContext.restoreGraphicsState()
    try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: "\(out)/\(name).png"))
}
func stroke(_ c: CGContext, _ color: NSColor, _ wd: CGFloat, _ p: CGPath) { c.setStrokeColor(color.cgColor); c.setLineWidth(wd); c.addPath(p); c.strokePath() }

/* Os desenhos, em coordenadas de 300×220 (origem embaixo, à esquerda). */
let desenhos: [(String, (CGContext) -> Void)] = [
    ("painel", { c in
        stroke(c, red, 8, CGPath(roundedRect: CGRect(x: 20, y: 40, width: 260, height: 140), cornerWidth: 30, cornerHeight: 30, transform: nil))
        let m = CGMutablePath(); m.move(to: CGPoint(x: 110, y: 70)); m.addLine(to: CGPoint(x: 150, y: 150)); m.addLine(to: CGPoint(x: 190, y: 70)); m.addLine(to: CGPoint(x: 150, y: 90)); m.closeSubpath()
        stroke(c, red, 7, m)
        let a = CGMutablePath(); a.addArc(center: CGPoint(x: 65, y: 110), radius: 28, startAngle: .pi * 1.2, endAngle: -.pi * 0.2, clockwise: true); a.move(to: CGPoint(x: 263, y: 110)); a.addArc(center: CGPoint(x: 235, y: 110), radius: 28, startAngle: 0, endAngle: .pi * 2, clockwise: false)
        stroke(c, white, 5, a)
    }),
    ("seta", { c in
        stroke(c, white, 7, CGPath(roundedRect: CGRect(x: 80, y: 40, width: 140, height: 140), cornerWidth: 18, cornerHeight: 18, transform: nil))
        let s = CGMutablePath(); s.move(to: CGPoint(x: 130, y: 60)); s.addLine(to: CGPoint(x: 130, y: 120)); s.addLine(to: CGPoint(x: 175, y: 120)); s.move(to: CGPoint(x: 160, y: 135)); s.addLine(to: CGPoint(x: 178, y: 120)); s.addLine(to: CGPoint(x: 160, y: 105))
        stroke(c, white, 8, s)
        let x = CGMutablePath(); x.move(to: CGPoint(x: 60, y: 25)); x.addLine(to: CGPoint(x: 240, y: 195))
        stroke(c, red, 10, x)
    }),
    ("celular", { c in
        stroke(c, red, 8, CGPath(roundedRect: CGRect(x: 40, y: 30, width: 80, height: 160), cornerWidth: 16, cornerHeight: 16, transform: nil))
        stroke(c, red, 8, CGPath(roundedRect: CGRect(x: 170, y: 70, width: 110, height: 80), cornerWidth: 18, cornerHeight: 18, transform: nil))
        let l = CGMutablePath(); l.move(to: CGPoint(x: 128, y: 110)); l.addLine(to: CGPoint(x: 162, y: 110)); l.move(to: CGPoint(x: 150, y: 122)); l.addLine(to: CGPoint(x: 164, y: 110)); l.addLine(to: CGPoint(x: 150, y: 98))
        stroke(c, white, 6, l)
    }),
    ("logs", { c in
        stroke(c, red, 8, CGPath(roundedRect: CGRect(x: 85, y: 20, width: 130, height: 180), cornerWidth: 12, cornerHeight: 12, transform: nil))
        let l = CGMutablePath(); for y in [160, 135, 110] { l.move(to: CGPoint(x: 110, y: y)); l.addLine(to: CGPoint(x: 190, y: y)) }
        stroke(c, white, 6, l)
        let d = CGMutablePath(); d.move(to: CGPoint(x: 150, y: 95)); d.addLine(to: CGPoint(x: 150, y: 45)); d.move(to: CGPoint(x: 130, y: 65)); d.addLine(to: CGPoint(x: 150, y: 45)); d.addLine(to: CGPoint(x: 170, y: 65))
        stroke(c, red, 7, d)
    })
]

/* Faixa livre para o texto: 3 linhas de 56 e a margem de cima (35), arredondada. */
let faixa: CGFloat = 220
let escala: CGFloat = 1.6
for (nome, desenha) in desenhos {
    png(nome, 300, 220, desenha)
    for (sufixo, y0) in [("baixo", faixa), ("cima", CGFloat(0))] {
        png("\(nome)-\(sufixo)", W, H) { c in
            let livre = CGFloat(H) - faixa
            c.translateBy(x: (CGFloat(W) - 300 * escala) / 2, y: y0 + (livre - 220 * escala) / 2)
            c.scaleBy(x: escala, y: escala)
            desenha(c)
        }
    }
}

/* A régua: borda, grade de 100 com os números e, a partir de baixo e de cima,
 * as faixas de 56 em que cabem as linhas de texto. */
png("regua", W, H) { c in
    stroke(c, red, 6, CGPath(rect: CGRect(x: 3, y: 3, width: W - 6, height: H - 6), transform: nil))
    let g = CGMutablePath()
    for x in stride(from: 100, to: W, by: 100) { g.move(to: CGPoint(x: x, y: 0)); g.addLine(to: CGPoint(x: x, y: H)) }
    for y in stride(from: 100, to: H, by: 100) { g.move(to: CGPoint(x: 0, y: y)); g.addLine(to: CGPoint(x: W, y: y)) }
    stroke(c, NSColor(calibratedWhite: 0.6, alpha: 1), 2, g)
    let t = CGMutablePath()
    for i in 1...4 {
        let y = CGFloat(56 * i)
        t.move(to: CGPoint(x: 0, y: y)); t.addLine(to: CGPoint(x: 60, y: y))
        t.move(to: CGPoint(x: 0, y: CGFloat(H) - y)); t.addLine(to: CGPoint(x: 60, y: CGFloat(H) - y))
    }
    stroke(c, white, 5, t)
    let centro = CGMutablePath(); centro.move(to: CGPoint(x: W / 2 - 30, y: H / 2)); centro.addLine(to: CGPoint(x: W / 2 + 30, y: H / 2)); centro.move(to: CGPoint(x: W / 2, y: H / 2 - 30)); centro.addLine(to: CGPoint(x: W / 2, y: H / 2 + 30))
    stroke(c, red, 5, centro)
    let attrs: [NSAttributedString.Key: Any] = [.font: NSFont.boldSystemFont(ofSize: 26), .foregroundColor: white]
    for x in stride(from: 100, to: W, by: 100) { NSString(string: "\(x)").draw(at: NSPoint(x: x + 4, y: H / 2 + 6), withAttributes: attrs) }
    for y in stride(from: 100, to: H, by: 100) { NSString(string: "\(H - y)").draw(at: NSPoint(x: W / 2 + 6, y: y + 4), withAttributes: attrs) }
    NSString(string: "957×639").draw(at: NSPoint(x: 20, y: H - 50), withAttributes: attrs)
}
