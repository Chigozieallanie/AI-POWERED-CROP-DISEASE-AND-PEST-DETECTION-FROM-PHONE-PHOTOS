import 'dart:convert';
import 'dart:math';

import 'package:flutter/services.dart';

import '../domain/models.dart';
import 'services.dart';

/// Content bundled inside the app, so everything works offline.
class AssetContentRepository implements ContentRepository {
  AssetContentRepository._(this._classes, this._advice, this._places);

  final Map<String, ProblemClass> _classes;
  final Map<String, Advice> _advice;
  final List<Place> _places;

  static Future<AssetContentRepository> load(AssetBundle bundle) async {
    final classes = <String, ProblemClass>{};
    for (final item in jsonDecode(await bundle.loadString('assets/content/classes.json')) as List) {
      final map = item as Map<String, dynamic>;
      classes[map['id'] as String] = ProblemClass(
        id: map['id'] as String,
        crop: Crop.values.byName(map['crop'] as String),
        kind: ClassKind.values.byName(map['kind'] as String),
        name: map['name'] as String,
        technicalName: map['technical_name'] as String?,
        referralType: PlaceType.fromCode(map['referral_type'] as String?),
      );
    }

    final advice = <String, Advice>{};
    for (final item in jsonDecode(await bundle.loadString('assets/content/advice.en.json')) as List) {
      final map = item as Map<String, dynamic>;
      List<String> list(String key) => [for (final v in (map[key] as List? ?? const [])) v as String];
      advice[map['class_id'] as String] = Advice(
        classId: map['class_id'] as String,
        stepsNow: list('steps_now'),
        prevention: list('prevention'),
        doNot: list('do_not'),
        safety: list('safety'),
        reviewed: map['review_status'] == 'reviewed',
        reviewer: map['reviewer'] as String?,
      );
    }

    return AssetContentRepository._(
      classes,
      advice,
      parsePlacesCsv(await bundle.loadString('assets/content/sample_places.csv')),
    );
  }

  @override
  bool get isDemoContent => _advice.values.any((a) => !a.reviewed) || _places.any((p) => p.isSample);

  @override
  ProblemClass? problemClass(String id) => _classes[id];

  @override
  List<ProblemClass> library(Crop crop) =>
      _classes.values.where((c) => c.crop == crop && c.kind != ClassKind.healthy).toList()
        ..sort((a, b) => a.name.compareTo(b.name));

  @override
  Advice? advice(String classId) => _advice[classId];

  @override
  List<Place> places() => List.unmodifiable(_places);

  @override
  Place? place(int id) {
    for (final place in _places) {
      if (place.id == id) return place;
    }
    return null;
  }

  @override
  List<String> districts() => _places.map((p) => p.district).toSet().toList()..sort();
}

/// Parses the places CSV. Fields must not contain commas.
List<Place> parsePlacesCsv(String text) {
  final lines = const LineSplitter().convert(text).where((l) => l.trim().isNotEmpty).toList();
  if (lines.isEmpty) return const [];
  final header = lines.first.split(',');
  final places = <Place>[];
  for (var i = 1; i < lines.length; i++) {
    final cells = lines[i].split(',');
    final row = {for (var c = 0; c < header.length; c++) header[c]: c < cells.length ? cells[c].trim() : ''};
    String? optional(String key) => (row[key] ?? '').isEmpty ? null : row[key];
    final type = PlaceType.fromCode(row['type']);
    if (type == null) continue;
    places.add(Place(
      id: i,
      type: type,
      name: row['name'] ?? '',
      phone: optional('phone'),
      latitude: double.parse(row['latitude']!),
      longitude: double.parse(row['longitude']!),
      district: row['district'] ?? '',
      landmark: optional('landmark'),
      hours: optional('hours'),
      stocks: optional('stocks'),
      certified: row['certified']?.toLowerCase() == 'true',
      lastChecked: optional('last_checked'),
      source: optional('source'),
      // A place is sample data unless the file says otherwise.
      isSample: (row['is_sample'] ?? 'true').toLowerCase() != 'false',
    ));
  }
  return places;
}

/// Straight-line distance in kilometres.
double haversineKm(double lat1, double lng1, double lat2, double lng2) {
  const earthRadiusKm = 6371.0;
  double rad(double degrees) => degrees * pi / 180;
  final dLat = rad(lat2 - lat1);
  final dLng = rad(lng2 - lng1);
  final a = sin(dLat / 2) * sin(dLat / 2) + cos(rad(lat1)) * cos(rad(lat2)) * sin(dLng / 2) * sin(dLng / 2);
  return earthRadiusKm * 2 * atan2(sqrt(a), sqrt(1 - a));
}

List<PlaceWithDistance> nearestPlaces(List<Place> places, PlaceType type, double lat, double lng, {int limit = 20}) {
  final matches = [
    for (final place in places.where((p) => p.type == type))
      PlaceWithDistance(place, haversineKm(lat, lng, place.latitude, place.longitude)),
  ]..sort((a, b) => a.distanceKm!.compareTo(b.distanceKm!));
  return matches.take(limit).toList();
}
