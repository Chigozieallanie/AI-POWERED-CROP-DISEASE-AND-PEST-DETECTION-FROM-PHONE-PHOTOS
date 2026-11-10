import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'data/demo_diagnosis.dart';
import 'data/services.dart';
import 'domain/models.dart';

/// Overridden in main() once assets are loaded.
final contentProvider = Provider<ContentRepository>((ref) => throw UnimplementedError());

/// Overridden in main().
final preferencesProvider = Provider<SharedPreferences>((ref) => throw UnimplementedError());

final diagnosisProvider = Provider<DiagnosisService>((ref) => DemoDiagnosisService());

/// The support number. Empty means no agreed number exists, so call buttons stay hidden.
const supportPhone = String.fromEnvironment('SUPPORT_PHONE');

class ScansNotifier extends Notifier<List<PlantResult>> {
  @override
  List<PlantResult> build() => const [];

  void add(PlantResult result) => state = [result, ...state];

  void delete(String id) => state = state.where((s) => s.id != id).toList();

  void deleteAll() => state = const [];

  PlantResult? byId(String id) {
    for (final scan in state) {
      if (scan.id == id) return scan;
    }
    return null;
  }
}

final scansProvider = NotifierProvider<ScansNotifier, List<PlantResult>>(ScansNotifier.new);

class SettingsNotifier extends Notifier<bool> {
  static const _welcomeKey = 'welcome_done';
  static const _sharingKey = 'photo_sharing';
  static const _guideKey = 'guide_done';

  SharedPreferences get _prefs => ref.read(preferencesProvider);

  /// State is the photo-sharing choice. Off by default.
  @override
  bool build() => _prefs.getBool(_sharingKey) ?? false;

  bool get welcomeDone => _prefs.getBool(_welcomeKey) ?? false;

  bool get guideDone => _prefs.getBool(_guideKey) ?? false;

  Future<void> finishWelcome({required bool sharePhotos}) async {
    await _prefs.setBool(_welcomeKey, true);
    await setSharing(sharePhotos);
  }

  Future<void> finishGuide() => _prefs.setBool(_guideKey, true);

  Future<void> setSharing(bool value) async {
    await _prefs.setBool(_sharingKey, value);
    state = value;
  }
}

final settingsProvider = NotifierProvider<SettingsNotifier, bool>(SettingsNotifier.new);
