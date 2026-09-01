// facecheck: print "<path>\t<faces>\t<largest face height as fraction of frame>" for each image.
// Apple Vision face rectangles; used to keep every B-roll window free of a readable face.
import Foundation
import Vision
import AppKit

let args = Array(CommandLine.arguments.dropFirst())
for path in args {
    guard let img = NSImage(contentsOfFile: path), let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        print("\(path)\tERR\t0"); continue
    }
    let req = VNDetectFaceRectanglesRequest()
    let handler = VNImageRequestHandler(cgImage: cg, options: [:])
    do { try handler.perform([req]) } catch { print("\(path)\tERR\t0"); continue }
    let faces = req.results ?? []
    let biggest = faces.map { $0.boundingBox.height }.max() ?? 0
    print("\(path)\t\(faces.count)\t\(String(format: "%.3f", biggest))")
}
