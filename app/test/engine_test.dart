import 'dart:math' as math;

import 'package:crop_check/data/tflite_diagnosis.dart';
import 'package:crop_check/domain/models.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image/image.dart' as img;

void main() {
  test('dark and flat photos fail the quality check', () {
    expect(qualityStatus(img.Image(width: 300, height: 300)), PhotoStatus.tooDark);
    final flat = img.Image(width: 300, height: 300)..clear(img.ColorRgb8(128, 128, 128));
    expect(qualityStatus(flat), PhotoStatus.tooBlurry);
  });

  test('textured photo passes the quality check', () {
    final rng = math.Random(1);
    final noisy = img.Image(width: 300, height: 300);
    for (final p in noisy) {
      p.setRgb(40 + rng.nextInt(180), 40 + rng.nextInt(180), 40 + rng.nextInt(180));
    }
    expect(qualityStatus(noisy), isNull);
  });

  test('model input keeps the centre and has NHWC shape', () {
    final image = img.Image(width: 400, height: 300);
    image.setPixelRgb(200, 150, 255, 0, 0);
    final input = toModelInput(image, 224, 0.6);
    expect(input.length, 224 * 224 * 3);
    final centre = (112 * 224 + 112) * 3;
    expect(input[centre], greaterThan(0)); // The red centre pixel survives the crop.
  });

  test('temperature 1 leaves probabilities unchanged', () {
    final p = calibrate([0.7, 0.2, 0.1], 1.0);
    expect(p[0], closeTo(0.7, 1e-9));
  });
}
