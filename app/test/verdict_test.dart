import 'dart:convert';
import 'dart:io';

import 'package:crop_check/data/asset_content.dart';
import 'package:crop_check/domain/models.dart';
import 'package:crop_check/domain/verdict.dart';
import 'package:flutter_test/flutter_test.dart';

const _states = {
  'problem_found': VerdictState.problemFound,
  'weak_evidence': VerdictState.weakEvidence,
  'healthy': VerdictState.healthy,
  'not_sure': VerdictState.notSure,
};
const _certainties = {'weak': Certainty.weak, 'likely': Certainty.likely, 'very_likely': Certainty.veryLikely};

void main() {
  // The same file the backend tests use, so both copies of the rules agree.
  final data = jsonDecode(File('../content/verdict_cases.json').readAsStringSync()) as Map<String, dynamic>;
  final thresholds = (data['thresholds'] as Map).map((k, v) => MapEntry(k as String, (v as num).toDouble()));
  final experimental = {for (final e in data['experimental'] as List) e as String};

  group('shared verdict cases', () {
    for (final raw in data['cases'] as List) {
      final c = raw as Map<String, dynamic>;
      test(c['name'], () {
        final leaves = [
          for (final l in c['leaves'] as List) LeafScore(l[0] as String, (l[1] as num).toDouble()),
        ];
        final verdict = plantVerdict(leaves, thresholds, experimental: experimental);
        expect(verdict.state, _states[c['state']]);
        expect(
          [for (final f in verdict.findings) [f.label, f.certainty, f.leafCount]],
          [for (final f in c['findings'] as List) [f[0], _certainties[f[1]], f[2]]],
        );
      });
    }
  });

  test('places csv parses and sorts by distance', () {
    final places = parsePlacesCsv(File('../content/sample_places.csv').readAsStringSync());
    expect(places, isNotEmpty);
    expect(places.every((p) => p.isSample), isTrue);
    final nearest = nearestPlaces(places, PlaceType.dealer, 0.3960, 32.5740);
    expect(nearest.first.place.name, 'SAMPLE Agro-dealer A');
    expect(nearest[1].distanceKm, closeTo(7.2, 0.3));
  });
}
