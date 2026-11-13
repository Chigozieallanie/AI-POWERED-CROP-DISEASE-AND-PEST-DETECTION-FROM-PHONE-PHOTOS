import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'app.dart';
import 'data/asset_content.dart';
import 'data/demo_diagnosis.dart';
import 'data/services.dart';
import 'data/tflite_diagnosis.dart';
import 'providers.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final content = await AssetContentRepository.load(rootBundle);
  final preferences = await SharedPreferences.getInstance();
  DiagnosisService engine;
  try {
    engine = await TfliteDiagnosisService.load(rootBundle);
  } catch (error) {
    // Models missing or unreadable: keep the app usable, clearly marked as demo.
    debugPrint('Model load failed, using demo engine: $error');
    engine = DemoDiagnosisService();
  }
  runApp(
    ProviderScope(
      overrides: [
        contentProvider.overrideWithValue(content),
        preferencesProvider.overrideWithValue(preferences),
        diagnosisProvider.overrideWithValue(engine),
      ],
      child: const CropCheckApp(),
    ),
  );
}
