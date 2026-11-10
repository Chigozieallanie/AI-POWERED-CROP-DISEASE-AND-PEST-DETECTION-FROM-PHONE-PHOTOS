enum Crop {
  cassava('Cassava'),
  maize('Maize');

  const Crop(this.label);
  final String label;
}

enum PhotoStatus {
  accepted('Looks good'),
  tooBlurry('Too blurry. Hold the phone still and retake.'),
  tooDark('Too dark. Retake in daylight.'),
  notLeaf('This does not look like a leaf.'),
  wrongCrop('This looks like a different crop.');

  const PhotoStatus(this.message);
  final String message;
}

class PhotoCheck {
  const PhotoCheck(this.status);
  final PhotoStatus status;
}

enum VerdictState { problemFound, weakEvidence, healthy, notSure }

enum Certainty {
  weak('Possible, based on few leaves'),
  likely('Likely'),
  veryLikely('Very likely');

  const Certainty(this.label);
  final String label;
}

class Finding {
  const Finding({
    required this.classId,
    required this.certainty,
    required this.leafCount,
    required this.experimental,
  });

  final String classId;
  final Certainty certainty;
  final int leafCount;
  final bool experimental;
}

class PlantResult {
  const PlantResult({
    required this.id,
    required this.crop,
    required this.state,
    required this.findings,
    required this.acceptedLeaves,
    required this.imagePaths,
    required this.modelVersion,
    required this.createdAt,
  });

  final String id;
  final Crop crop;
  final VerdictState state;
  final List<Finding> findings;
  final int acceptedLeaves;
  final List<String> imagePaths;
  final String modelVersion;
  final DateTime createdAt;
}

enum ClassKind { disease, pest, healthy }

enum PlaceType {
  dealer('dealer', 'Certified dealer', 'Find a certified dealer'),
  cleanCuttings('clean_cuttings', 'Clean cuttings', 'Find clean cuttings'),
  extensionOffice('extension_office', 'Extension office', 'Find an extension office');

  const PlaceType(this.code, this.label, this.action);
  final String code;
  final String label;
  final String action;

  static PlaceType? fromCode(String? code) {
    for (final type in values) {
      if (type.code == code) return type;
    }
    return null;
  }
}

class ProblemClass {
  const ProblemClass({
    required this.id,
    required this.crop,
    required this.kind,
    required this.name,
    this.technicalName,
    this.referralType,
  });

  final String id;
  final Crop crop;
  final ClassKind kind;
  final String name;
  final String? technicalName;
  final PlaceType? referralType;
}

class Advice {
  const Advice({
    required this.classId,
    required this.stepsNow,
    required this.prevention,
    required this.doNot,
    required this.safety,
    required this.reviewed,
    this.reviewer,
  });

  final String classId;
  final List<String> stepsNow;
  final List<String> prevention;
  final List<String> doNot;
  final List<String> safety;
  final bool reviewed;
  final String? reviewer;
}

class Place {
  const Place({
    required this.id,
    required this.type,
    required this.name,
    required this.latitude,
    required this.longitude,
    required this.district,
    required this.certified,
    required this.isSample,
    this.phone,
    this.landmark,
    this.hours,
    this.stocks,
    this.lastChecked,
    this.source,
  });

  final int id;
  final PlaceType type;
  final String name;
  final double latitude;
  final double longitude;
  final String district;
  final bool certified;
  final bool isSample;
  final String? phone;
  final String? landmark;
  final String? hours;
  final String? stocks;
  final String? lastChecked;
  final String? source;
}

class PlaceWithDistance {
  const PlaceWithDistance(this.place, this.distanceKm);
  final Place place;
  final double? distanceKm;
}
