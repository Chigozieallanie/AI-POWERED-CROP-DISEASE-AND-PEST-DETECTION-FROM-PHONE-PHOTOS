import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../domain/models.dart';
import '../providers.dart';
import '../widgets/common.dart';
import 'history_screen.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final scans = ref.watch(scansProvider);
    final settings = ref.read(settingsProvider.notifier);
    final text = Theme.of(context).textTheme;

    void startScan(Crop crop) => context.push(settings.guideDone ? '/capture/${crop.name}' : '/guide/${crop.name}');

    return Scaffold(
      appBar: AppBar(
        title: const Text('Crop Check'),
        actions: [IconButton(onPressed: () => context.push('/settings'), icon: const Icon(Icons.settings_outlined))],
      ),
      body: Column(children: [
        const DemoBanner(),
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Row(children: [
                const Icon(Icons.wifi_off, size: 18),
                const SizedBox(width: 6),
                Text('Works without internet', style: text.bodyMedium),
              ]),
              const SizedBox(height: 16),
              Text('Which crop do you want to check?', style: text.titleLarge),
              const SizedBox(height: 12),
              Row(children: [
                for (final crop in Crop.values)
                  Expanded(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 4),
                      child: _CropTile(crop: crop, onTap: () => startScan(crop)),
                    ),
                  ),
              ]),
              if (scans.isNotEmpty) ...[
                const SectionTitle('Recent checks'),
                for (final scan in scans.take(3)) ScanTile(scan: scan),
              ],
              const SectionTitle('Need help?'),
              Card(
                child: ListTile(
                  leading: const Icon(Icons.place_outlined),
                  title: const Text('Nearby help'),
                  subtitle: const Text('Dealers, clean cuttings, extension offices'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => context.go('/help'),
                ),
              ),
              const SizedBox(height: 8),
              const SupportCallButton(),
            ],
          ),
        ),
      ]),
    );
  }
}

class _CropTile extends StatelessWidget {
  const _CropTile({required this.crop, required this.onTap});
  final Crop crop;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Card(
      color: colors.primaryContainer,
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 28),
          child: Column(children: [
            Icon(crop == Crop.cassava ? Icons.grass : Icons.agriculture, size: 48, color: colors.onPrimaryContainer),
            const SizedBox(height: 8),
            Text(crop.label, style: Theme.of(context).textTheme.titleMedium?.copyWith(color: colors.onPrimaryContainer)),
            Text('Check a plant', style: TextStyle(color: colors.onPrimaryContainer)),
          ]),
        ),
      ),
    );
  }
}
