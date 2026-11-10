import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../data/asset_content.dart';
import '../domain/models.dart';
import '../providers.dart';
import '../widgets/common.dart';

class NearbyScreen extends ConsumerStatefulWidget {
  const NearbyScreen({super.key, this.initialType});
  final PlaceType? initialType;

  @override
  ConsumerState<NearbyScreen> createState() => _NearbyScreenState();
}

class _NearbyScreenState extends ConsumerState<NearbyScreen> {
  late PlaceType _type = widget.initialType ?? PlaceType.dealer;
  Position? _position;
  bool _locating = true;
  String? _district;

  @override
  void initState() {
    super.initState();
    _locate();
  }

  Future<void> _locate() async {
    try {
      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) permission = await Geolocator.requestPermission();
      if (permission == LocationPermission.denied || permission == LocationPermission.deniedForever) {
        throw StateError('denied');
      }
      // Last known position first: it works offline and is instant.
      final position = await Geolocator.getLastKnownPosition() ??
          await Geolocator.getCurrentPosition(
            locationSettings: const LocationSettings(accuracy: LocationAccuracy.medium, timeLimit: Duration(seconds: 15)),
          );
      if (mounted) setState(() => _position = position);
    } catch (_) {
      // No permission or no fix: the district picker is shown instead.
    } finally {
      if (mounted) setState(() => _locating = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final content = ref.watch(contentProvider);
    final List<PlaceWithDistance> results;
    if (_position != null) {
      results = nearestPlaces(content.places(), _type, _position!.latitude, _position!.longitude);
    } else {
      results = [
        for (final p in content.places().where((p) => p.type == _type && (_district == null || p.district == _district)))
          PlaceWithDistance(p, null),
      ];
    }

    return Scaffold(
      appBar: AppBar(title: Text(_type.action)),
      body: Column(children: [
        const DemoBanner(),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
          child: SegmentedButton<PlaceType>(
            showSelectedIcon: false,
            segments: [
              for (final type in PlaceType.values) ButtonSegment(value: type, label: Text(type.label, textAlign: TextAlign.center)),
            ],
            selected: {_type},
            onSelectionChanged: (selection) => setState(() => _type = selection.first),
          ),
        ),
        if (_locating) const LinearProgressIndicator(),
        if (!_locating && _position == null)
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
            child: DropdownButtonFormField<String?>(
              initialValue: _district,
              decoration: const InputDecoration(labelText: 'Location is off. Choose your district'),
              items: [
                const DropdownMenuItem(value: null, child: Text('All districts')),
                for (final district in content.districts()) DropdownMenuItem(value: district, child: Text(district)),
              ],
              onChanged: (value) => setState(() => _district = value),
            ),
          ),
        const Padding(
          padding: EdgeInsets.fromLTRB(16, 12, 16, 4),
          child: Text('Phone first to check they have what you need in stock.'),
        ),
        Expanded(
          child: results.isEmpty
              ? const Padding(padding: EdgeInsets.all(16), child: SupportCallButton())
              : ListView.builder(
                  padding: const EdgeInsets.symmetric(horizontal: 8),
                  itemCount: results.length,
                  itemBuilder: (context, i) => _PlaceTile(item: results[i]),
                ),
        ),
      ]),
    );
  }
}

class _PlaceTile extends StatelessWidget {
  const _PlaceTile({required this.item});
  final PlaceWithDistance item;

  @override
  Widget build(BuildContext context) {
    final place = item.place;
    final details = [
      if (item.distanceKm != null) '${item.distanceKm!.toStringAsFixed(1)} km',
      place.landmark ?? place.district,
      if (place.lastChecked != null) 'checked ${place.lastChecked}',
    ].join(' · ');
    return Card(
      child: ListTile(
        onTap: () => context.push('/place/${place.id}'),
        title: Text(place.name),
        subtitle: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(details),
          Wrap(spacing: 6, children: [
            if (place.certified) const Chip(label: Text('Certified'), visualDensity: VisualDensity.compact),
            if (place.isSample) const Chip(label: Text('Sample data'), visualDensity: VisualDensity.compact),
          ]),
        ]),
        trailing: place.phone == null
            ? null
            : IconButton(
                tooltip: 'Call',
                onPressed: () => launchUrl(Uri(scheme: 'tel', path: place.phone)),
                icon: const Icon(Icons.call),
              ),
      ),
    );
  }
}
