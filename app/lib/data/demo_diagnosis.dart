import '../domain/models.dart';
import '../domain/verdict.dart';
import 'services.dart';

/// Stand-in engine used until the real TFLite engine is connected.
/// It accepts every photo and reports a fixed problem, and the app labels it as a demo.
class DemoDiagnosisService implements DiagnosisService {
  static const _thresholds = {
    'healthy': 0.7,
    'cassava_mosaic': 0.7,
    'maize_streak_virus': 0.7,
  };

  @override
  bool get isDemo => true;

  @override
  Future<PhotoCheck> checkPhoto(Crop crop, String imagePath) async {
    await Future<void>.delayed(const Duration(milliseconds: 300));
    return const PhotoCheck(PhotoStatus.accepted);
  }

  @override
  Future<PlantResult> diagnose(Crop crop, List<String> imagePaths) async {
    await Future<void>.delayed(const Duration(milliseconds: 600));
    final label = crop == Crop.cassava ? 'cassava_mosaic' : 'maize_streak_virus';
    final verdict = plantVerdict([for (final _ in imagePaths) LeafScore(label, 0.9)], _thresholds);
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
      modelVersion: 'demo',
      createdAt: now,
    );
  }
}
