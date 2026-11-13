import 'dart:convert';
import 'dart:isolate';
import 'dart:math' as math;
import 'dart:typed_data';

import 'package:flutter/services.dart';
import 'package:image/image.dart' as img;
import 'package:tflite_flutter/tflite_flutter.dart';

import '../domain/models.dart';
import '../domain/verdict.dart';
import 'services.dart';

// Same starting values as the backend (backend/app/config.py).
const minSharpness = 30.0;
const minBrightness = 40.0;
const gateMinScore = 0.6;

class ModelCard {
  ModelCard.fromJson(Map<String, dynamic> json)
      : name = json['name'] as String,
        version = json['version'] as String,
        inputSize = json['input_size'] as int,
        classes = [for (final c in json['classes'] as List) c as String],
        temperature = (json['temperature'] as num).toDouble(),
        thresholds = {
          for (final e in (json['thresholds'] as Map).entries) e.key as String: (e.value as num).toDouble(),
        },
        experimental = {for (final c in (json['experimental_classes'] as List? ?? const [])) c as String},
        centerCrop = (json['center_crop'] as num? ?? 1.0).toDouble();

  final String name;
  final String version;
  final int inputSize;
  final List<String> classes;
  final double temperature;
  final Map<String, double> thresholds;
  final Set<String> experimental;
  final double centerCrop;
}

class _Model {
  _Model(this.card, this.interpreter);
  final ModelCard card;
  final Interpreter interpreter;

  /// Returns (label, calibrated score) for one prepared RGB image.
  (String, double) top(Float32List input) {
    final output = Float32List(card.classes.length);
    interpreter.run(input.buffer.asUint8List(), output.buffer);
    final probabilities = calibrate(output, card.temperature);
    var best = 0;
    for (var i = 1; i < probabilities.length; i++) {
      if (probabilities[i] > probabilities[best]) best = i;
    }
    return (card.classes[best], probabilities[best]);
  }
}

List<double> calibrate(List<double> probabilities, double temperature) {
  final logits = [for (final p in probabilities) math.log(p.clamp(1e-12, 1.0)) / temperature];
  final peak = logits.reduce(math.max);
  final exps = [for (final l in logits) math.exp(l - peak)];
  final sum = exps.reduce((a, b) => a + b);
  return [for (final e in exps) e / sum];
}

/// Work done off the main thread: decode, check quality, build model inputs.
class PreparedPhoto {
  const PreparedPhoto(this.status, this.gateInput, this.cropInput);
  final PhotoStatus? status; // Set only when the photo fails the quality check.
  final Float32List? gateInput;
  final Float32List? cropInput;
}

class PrepareRequest {
  const PrepareRequest(this.path, this.gateSize, this.cropSize, this.cropKeep);
  final String path;
  final int gateSize;
  final int cropSize;
  final double cropKeep;
}

Future<PreparedPhoto> preparePhoto(PrepareRequest request) async {
  final decoded = await img.decodeImageFile(request.path);
  if (decoded == null) return const PreparedPhoto(PhotoStatus.notLeaf, null, null);
  final image = img.bakeOrientation(decoded).convert(numChannels: 3);

  final quality = qualityStatus(image);
  if (quality != null) return PreparedPhoto(quality, null, null);
  return PreparedPhoto(
    null,
    toModelInput(image, request.gateSize, 1.0),
    toModelInput(image, request.cropSize, request.cropKeep),
  );
}

/// Brightness and sharpness, as in the backend: grayscale scaled to fit 512 px.
PhotoStatus? qualityStatus(img.Image image) {
  final scale = math.min(1.0, 512 / math.max(image.width, image.height));
  final small = scale < 1.0
      ? img.copyResize(
          image,
          width: (image.width * scale).round(),
          height: (image.height * scale).round(),
          interpolation: img.Interpolation.average,
        )
      : image;
  final w = small.width, h = small.height;
  final gray = Float64List(w * h);
  var total = 0.0;
  for (var y = 0; y < h; y++) {
    for (var x = 0; x < w; x++) {
      final p = small.getPixel(x, y);
      final v = (p.r * 299 + p.g * 587 + p.b * 114) / 1000;
      gray[y * w + x] = v;
      total += v;
    }
  }
  if (total / gray.length < minBrightness) return PhotoStatus.tooDark;
  if (w < 3 || h < 3) return PhotoStatus.tooBlurry;

  var sum = 0.0, sumSq = 0.0;
  var count = 0;
  for (var y = 1; y < h - 1; y++) {
    for (var x = 1; x < w - 1; x++) {
      final i = y * w + x;
      final lap = gray[i - w] + gray[i + w] + gray[i - 1] + gray[i + 1] - 4 * gray[i];
      sum += lap;
      sumSq += lap * lap;
      count++;
    }
  }
  final mean = sum / count;
  final variance = sumSq / count - mean * mean;
  return variance < minSharpness ? PhotoStatus.tooBlurry : null;
}

/// Centre square keeping [keep] of the short side, resized, as RGB 0-255 floats (NHWC).
Float32List toModelInput(img.Image image, int size, double keep) {
  final side = math.max(1, (math.min(image.width, image.height) * keep).round());
  final square = img.copyCrop(
    image,
    x: (image.width - side) ~/ 2,
    y: (image.height - side) ~/ 2,
    width: side,
    height: side,
  );
  // Averaging approximates the backend's antialiased resize when shrinking.
  final resized = img.copyResize(square, width: size, height: size, interpolation: img.Interpolation.average);
  final bytes = resized.getBytes(order: img.ChannelOrder.rgb);
  final input = Float32List(bytes.length);
  for (var i = 0; i < bytes.length; i++) {
    input[i] = bytes[i].toDouble();
  }
  return input;
}

class _LeafOutcome {
  const _LeafOutcome(this.status, [this.label, this.score]);
  final PhotoStatus status;
  final String? label;
  final double? score;
}

/// Runs the three models on the phone, with no internet needed.
class TfliteDiagnosisService implements DiagnosisService {
  TfliteDiagnosisService._(this._gate, this._crops);

  final _Model _gate;
  final Map<Crop, _Model> _crops;
  final Map<String, _LeafOutcome> _cache = {};

  static Future<TfliteDiagnosisService> load(AssetBundle bundle) async {
    Future<_Model> model(String name) async {
      final card = ModelCard.fromJson(
        jsonDecode(await bundle.loadString('assets/models/$name/model_card.json')) as Map<String, dynamic>,
      );
      final options = InterpreterOptions()..threads = 2;
      final interpreter = await Interpreter.fromAsset('assets/models/$name/model.tflite', options: options);
      return _Model(card, interpreter);
    }

    return TfliteDiagnosisService._(
      await model('gate'),
      {Crop.cassava: await model('cassava'), Crop.maize: await model('maize')},
    );
  }

  @override
  bool get isDemo => false;

  String get modelVersions =>
      'gate ${_gate.card.version}, cassava ${_crops[Crop.cassava]!.card.version}, maize ${_crops[Crop.maize]!.card.version}';

  Future<_LeafOutcome> _examine(Crop crop, String path) async {
    final key = '${crop.name}|$path';
    final cached = _cache[key];
    if (cached != null) return cached;

    final cropModel = _crops[crop]!;
    final prepared = await Isolate.run(
      () => preparePhoto(PrepareRequest(path, _gate.card.inputSize, cropModel.card.inputSize, cropModel.card.centerCrop)),
    );
    _LeafOutcome outcome;
    if (prepared.status != null) {
      outcome = _LeafOutcome(prepared.status!);
    } else {
      final (gateLabel, gateScore) = _gate.top(prepared.gateInput!);
      if (gateLabel == 'other' || gateScore < gateMinScore) {
        outcome = const _LeafOutcome(PhotoStatus.notLeaf);
      } else if (gateLabel != '${crop.name}_leaf') {
        outcome = const _LeafOutcome(PhotoStatus.wrongCrop);
      } else {
        final (label, score) = cropModel.top(prepared.cropInput!);
        outcome = _LeafOutcome(PhotoStatus.accepted, label, score);
      }
    }
    _cache[key] = outcome;
    return outcome;
  }

  @override
  Future<PhotoCheck> checkPhoto(Crop crop, String imagePath) async =>
      PhotoCheck((await _examine(crop, imagePath)).status);

  @override
  Future<PlantResult> diagnose(Crop crop, List<String> imagePaths) async {
    final card = _crops[crop]!.card;
    final scores = <LeafScore>[];
    for (final path in imagePaths) {
      final outcome = await _examine(crop, path);
      if (outcome.status == PhotoStatus.accepted) scores.add(LeafScore(outcome.label!, outcome.score!));
    }
    final verdict = plantVerdict(scores, card.thresholds, experimental: card.experimental);
    final now = DateTime.now();
    return PlantResult(
      id: now.microsecondsSinceEpoch.toString(),
      crop: crop,
      state: verdict.state,
      findings: [
        for (final f in verdict.findings)
          Finding(classId: f.label, certainty: f.certainty, leafCount: f.leafCount, experimental: f.experimental),
      ],
      acceptedLeaves: verdict.acceptedLeaves,
      imagePaths: List.unmodifiable(imagePaths),
      modelVersion: card.version,
      createdAt: now,
    );
  }
}
