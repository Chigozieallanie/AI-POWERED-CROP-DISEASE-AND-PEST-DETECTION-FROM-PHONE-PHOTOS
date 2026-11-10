import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../providers.dart';
import '../widgets/common.dart';

class PlaceScreen extends ConsumerWidget {
  const PlaceScreen({super.key, required this.placeId});
  final int placeId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final place = ref.watch(contentProvider).place(placeId);
    if (place == null) {
      return Scaffold(appBar: AppBar(), body: const Center(child: Text('This place no longer exists.')));
    }

    Future<void> directions() async {
      final uri = Uri.parse('geo:${place.latitude},${place.longitude}?q=${place.latitude},${place.longitude}');
      final opened = await canLaunchUrl(uri) && await launchUrl(uri);
      if (!opened && context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('No map app is available on this phone.')));
      }
    }

    Widget row(IconData icon, String label, String? value) => value == null
        ? const SizedBox.shrink()
        : ListTile(leading: Icon(icon), title: Text(label), subtitle: Text(value));

    return Scaffold(
      appBar: AppBar(title: Text(place.name)),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (place.isSample)
            const Card(child: ListTile(leading: Icon(Icons.info_outline), title: Text('Sample data, not a real place'))),
          row(Icons.store_outlined, 'Type', placeTypeLabel(place.type)),
          row(Icons.verified_outlined, 'Certified', place.certified ? 'Yes' : 'Not confirmed'),
          row(Icons.place_outlined, 'Location', [place.landmark, place.district].whereType<String>().join(', ')),
          row(Icons.schedule, 'Opening hours', place.hours),
          row(Icons.inventory_2_outlined, 'Stocks', place.stocks),
          row(Icons.fact_check_outlined, 'Last checked', place.lastChecked),
          row(Icons.source_outlined, 'Source', place.source),
          const SizedBox(height: 16),
          Wrap(spacing: 8, runSpacing: 8, children: [
            if (place.phone != null)
              FilledButton.icon(
                onPressed: () => launchUrl(Uri(scheme: 'tel', path: place.phone)),
                icon: const Icon(Icons.call),
                label: const Text('Call'),
              ),
            OutlinedButton.icon(onPressed: directions, icon: const Icon(Icons.directions), label: const Text('Directions')),
            TextButton.icon(
              onPressed: () => ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Thank you. Your report will be sent when you are online.')),
              ),
              icon: const Icon(Icons.flag_outlined),
              label: const Text('Report wrong information'),
            ),
          ]),
        ],
      ),
    );
  }
}
