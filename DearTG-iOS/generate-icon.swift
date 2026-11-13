import AppKit
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers

let size = 1024
let colorSpace = CGColorSpaceCreateDeviceRGB()
guard let context = CGContext(data: nil, width: size, height: size, bitsPerComponent: 8,
                              bytesPerRow: size * 4, space: colorSpace,
                              bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else {
    fatalError("Could not create icon context")
}
let bounds = CGRect(x: 0, y: 0, width: size, height: size)
let background = CGPath(roundedRect: bounds.insetBy(dx: 12, dy: 12),
                        cornerWidth: 224, cornerHeight: 224, transform: nil)
context.addPath(background)
context.clip()

let colors = [
    CGColor(red: 0.07, green: 0.20, blue: 0.23, alpha: 1),
    CGColor(red: 0.12, green: 0.48, blue: 0.43, alpha: 1),
    CGColor(red: 0.27, green: 0.72, blue: 0.61, alpha: 1)
] as CFArray
let locations: [CGFloat] = [0, 0.58, 1]
let gradient = CGGradient(colorsSpace: colorSpace, colors: colors, locations: locations)!
context.drawLinearGradient(gradient, start: CGPoint(x: 0, y: 0),
                           end: CGPoint(x: size, y: size), options: [])

context.saveGState()
context.setShadow(offset: CGSize(width: 0, height: -18), blur: 34,
                  color: CGColor(gray: 0, alpha: 0.22))
let mainBubble = CGMutablePath()
mainBubble.move(to: CGPoint(x: 244, y: 642))
mainBubble.addCurve(to: CGPoint(x: 382, y: 786), control1: CGPoint(x: 244, y: 730), control2: CGPoint(x: 306, y: 786))
mainBubble.addLine(to: CGPoint(x: 608, y: 786))
mainBubble.addCurve(to: CGPoint(x: 790, y: 604), control1: CGPoint(x: 790, y: 786), control2: CGPoint(x: 790, y: 704))
mainBubble.addLine(to: CGPoint(x: 790, y: 438))
mainBubble.addCurve(to: CGPoint(x: 608, y: 256), control1: CGPoint(x: 790, y: 338), control2: CGPoint(x: 708, y: 256))
mainBubble.addLine(to: CGPoint(x: 426, y: 256))
mainBubble.addCurve(to: CGPoint(x: 244, y: 438), control1: CGPoint(x: 326, y: 256), control2: CGPoint(x: 244, y: 338))
mainBubble.closeSubpath()
context.addPath(mainBubble)
context.setFillColor(CGColor(red: 0.97, green: 1, blue: 0.98, alpha: 1))
context.fillPath()
context.restoreGState()

let tail = CGMutablePath()
tail.move(to: CGPoint(x: 300, y: 650))
tail.addCurve(to: CGPoint(x: 274, y: 806), control1: CGPoint(x: 294, y: 720), control2: CGPoint(x: 270, y: 770))
tail.addCurve(to: CGPoint(x: 416, y: 764), control1: CGPoint(x: 326, y: 824), control2: CGPoint(x: 366, y: 792))
tail.closeSubpath()
context.addPath(tail)
context.setFillColor(CGColor(red: 0.97, green: 1, blue: 0.98, alpha: 1))
context.fillPath()

let smallBubble = CGMutablePath()
smallBubble.move(to: CGPoint(x: 470, y: 548))
smallBubble.addCurve(to: CGPoint(x: 570, y: 648), control1: CGPoint(x: 470, y: 604), control2: CGPoint(x: 514, y: 648))
smallBubble.addLine(to: CGPoint(x: 700, y: 648))
smallBubble.addCurve(to: CGPoint(x: 800, y: 548), control1: CGPoint(x: 800, y: 648), control2: CGPoint(x: 800, y: 604))
smallBubble.addLine(to: CGPoint(x: 800, y: 470))
smallBubble.addCurve(to: CGPoint(x: 700, y: 370), control1: CGPoint(x: 800, y: 414), control2: CGPoint(x: 756, y: 370))
smallBubble.addLine(to: CGPoint(x: 570, y: 370))
smallBubble.addCurve(to: CGPoint(x: 470, y: 470), control1: CGPoint(x: 470, y: 414), control2: CGPoint(x: 470, y: 458))
smallBubble.closeSubpath()
context.addPath(smallBubble)
context.setFillColor(CGColor(red: 0.20, green: 0.62, blue: 0.55, alpha: 1))
context.fillPath()

for x in [550, 635, 720] {
    context.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 0.96))
    context.fillEllipse(in: CGRect(x: x, y: 498, width: 28, height: 28))
}

guard let image = context.makeImage() else { fatalError("Could not render icon") }
let output = URL(fileURLWithPath: "Assets.xcassets/AppIcon.appiconset/AppIcon.png")
guard let destination = CGImageDestinationCreateWithURL(output as CFURL, UTType.png.identifier as CFString, 1, nil) else {
    fatalError("Could not create PNG destination")
}
CGImageDestinationAddImage(destination, image, nil)
guard CGImageDestinationFinalize(destination) else { fatalError("Could not write icon") }
print("Generated DearTG app icon at \(output.path)")
