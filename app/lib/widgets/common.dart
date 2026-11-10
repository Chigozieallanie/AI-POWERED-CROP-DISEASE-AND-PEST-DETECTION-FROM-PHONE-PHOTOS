import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../domain/models.dart';
import '../providers.dart';

/// Shown while results are made up or advice and places are unreviewed.
class DemoBanner extends ConsumerWidget {
  const DemoBanner({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final demoEngine = ref.watch(diagnosisProvider).isDemo;
    final demoContent = ref.watch(contentProvider).isDemoContent;
    if (!demoEngine && !demoContent) return const SizedBox.shrink();
    final message = demoEngine
        ? 'Demo: results are not real yet. Advice not yet reviewed.'
        : 'Demo: advice not yet reviewed. Places are sample data.';
    final colors = Theme.of(context).colorScheme;
    return Container(
      width: double.infinity,
      color: colors.tertiaryContainer,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(children: [
        Icon(Icons.info_outline, size: 18, color: colors.onTertiaryContainer),
        const SizedBox(width: 8),
        Expanded(child: Text(message, style: TextStyle(color: colors.onTertiaryContainer))),
      ]),
    );
  }
}

class SectionTitle extends StatelessWidget {
  const SectionTitle(this.text, {super.key});
  final String text;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(0, 20, 0, 8),
        child: Text(text, style: Theme.of(context).textTheme.titleMedium),
      );
}

class BulletList extends StatelessWidget {
  const BulletList(this.items, {super.key, this.numbered = false});
  final List<String> items;
  final bool numbered;

  @override
  Widget build(BuildContext context) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (var i = 0; i < items.length; i++)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                SizedBox(width: 24, child: Text(numbered ? '${i + 1}.' : '•')),
                Expanded(child: Text(items[i])),
              ]),
            ),
        ],
      );
}

class LeafThumb extends StatelessWidget {
  const LeafThumb(this.path, {super.key, this.size = 72});
  final String path;
  final double size;

  @override
  Widget build(BuildContext context) => ClipRRect(
        borderRadius: BorderRadius.circular(8),
        child: Image.file(
          File(path),
          width: size,
          height: size,
          fit: BoxFit.cover,
          cacheWidth: (size * 2).round(),
          errorBuilder: (_, _, _) => Container(
            width: size,
            height: size,
            color: Theme.of(context).colorScheme.surfaceContainerHighest,
            child: const Icon(Icons.broken_image_outlined),
          ),
        ),
      );
}

/// A call button that only exists when a real, agreed number is set.
class SupportCallButton extends StatelessWidget {
  const SupportCallButton({super.key, this.label = 'Call extension officer'});
  final String label;

  @override
  Widget build(BuildContext context) {
    if (supportPhone.isEmpty) {
      return const Text('Ask your nearest extension office for help.');
    }
    return OutlinedButton.icon(
      onPressed: () => launchUrl(Uri(scheme: 'tel', path: supportPhone)),
      icon: const Icon(Icons.call),
      label: Text(label),
    );
  }
}

String placeTypeLabel(PlaceType type) => type.label;

String formatDate(DateTime date) =>
    '${date.day.toString().padLeft(2, '0')}/${date.month.toString().padLeft(2, '0')}/${date.year}';
