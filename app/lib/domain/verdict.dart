/// Plant verdict rules from section 5.2 of the design.
///
/// The backend has a Python copy. Both must pass content/verdict_cases.json.
library;

import 'models.dart';

const healthyLabel = 'healthy';
const minLeavesForConfidence = 3;

class LeafScore {
  const LeafScore(this.label, this.score);
  final String label;
  final double score;
}

class VerdictFinding {
  const VerdictFinding(this.label, this.certainty, this.leafCount, this.experimental);
  final String label;
  final Certainty certainty;
  final int leafCount;
  final bool experimental;
}

class Verdict {
  const Verdict(this.state, this.acceptedLeaves, this.findings);
  final VerdictState state;
  final int acceptedLeaves;
  final List<VerdictFinding> findings;
}

Certainty _certainty(int count, int accepted, bool experimental) {
  if (count == 1 || accepted < minLeavesForConfidence) return Certainty.weak;
  if (!experimental && count >= 3 && count * 2 >= accepted) return Certainty.veryLikely;
  return Certainty.likely;
}

Verdict plantVerdict(
  List<LeafScore> leaves,
  Map<String, double> thresholds, {
  Set<String> experimental = const {},
}) {
  final accepted = leaves.length;
  final counts = <String, int>{};
  for (final leaf in leaves) {
    // A label with no threshold never counts, so a bad model card fails safe.
    final threshold = thresholds[leaf.label];
    if (threshold != null && leaf.score >= threshold) {
      counts[leaf.label] = (counts[leaf.label] ?? 0) + 1;
    }
  }

  final diseases = counts.entries.where((e) => e.key != healthyLabel).toList()
    ..sort((a, b) {
      final byCount = b.value.compareTo(a.value);
      return byCount != 0 ? byCount : a.key.compareTo(b.key);
    });
  final findings = [
    for (final entry in diseases)
      VerdictFinding(
        entry.key,
        _certainty(entry.value, accepted, experimental.contains(entry.key)),
        entry.value,
        experimental.contains(entry.key),
      ),
  ];

  if (findings.isNotEmpty) {
    final strong = findings.any((f) => f.certainty != Certainty.weak);
    return Verdict(strong ? VerdictState.problemFound : VerdictState.weakEvidence, accepted, findings);
  }
  if (accepted >= minLeavesForConfidence && counts[healthyLabel] == accepted) {
    return Verdict(VerdictState.healthy, accepted, const []);
  }
  return Verdict(VerdictState.notSure, accepted, const []);
}
