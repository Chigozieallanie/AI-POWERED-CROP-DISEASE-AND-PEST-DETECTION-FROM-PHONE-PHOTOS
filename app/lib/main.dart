import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'app.dart';
import 'data/asset_content.dart';
import 'providers.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final content = await AssetContentRepository.load(rootBundle);
  final preferences = await SharedPreferences.getInstance();
  runApp(
    ProviderScope(
      overrides: [
        contentProvider.overrideWithValue(content),
        preferencesProvider.overrideWithValue(preferences),
      ],
      child: const CropCheckApp(),
    ),
  );
}
