import '../domain/models.dart';

/// The contract between screens and the engine, from section 6 of the design.
/// Screens only use these, so the real model engine can replace the demo one.
abstract class DiagnosisService {
  /// True while no real models are installed and results are made up.
  bool get isDemo;

  Future<PhotoCheck> checkPhoto(Crop crop, String imagePath);

  Future<PlantResult> diagnose(Crop crop, List<String> imagePaths);
}

abstract class ContentRepository {
  /// True while advice is unreviewed or any place is sample data.
  bool get isDemoContent;

  ProblemClass? problemClass(String id);

  List<ProblemClass> library(Crop crop);

  Advice? advice(String classId);

  List<Place> places();

  Place? place(int id);

  List<String> districts();
}
