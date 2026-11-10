import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../domain/models.dart';
import '../providers.dart';
import '../widgets/common.dart';

class ResultScreen extends ConsumerWidget {
  const ResultScreen({super.key, required this.scanId});
  final String scanId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    ref.watch(scansProvider);
    final scan = ref.read(scansProvider.notifier).byId(scanId);
    if (scan == null) {
      return Scaffold(appBar: AppBar(), body: const Center(child: Text('This check no longer exists.')));
    }
    final content = ref.watch(contentProvider);
    final text = Theme.of(context).textTheme;

    Widget findingCard(Finding finding) {
      final problem = content.problemClass(finding.classId);
      final referral = problem?.referralType ?? PlaceType.extensionOffice;
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Expanded(child: Text(problem?.name ?? finding.classId, style: text.titleLarge)),
              Chip(label: Text(problem?.kind == ClassKind.pest ? 'Pest' : 'Disease')),
            ]),
            if (problem?.technicalName != null) Text(problem!.technicalName!, style: text.bodySmall),
            const SizedBox(height: 8),
            Text(finding.certainty.label, style: text.titleMedium),
            Text('Seen on ${finding.leafCount} of ${scan.acceptedLeaves} leaves'),
            if (finding.experimental)
              const Padding(
                padding: EdgeInsets.only(top: 4),
                child: Text('This check is still being tested.', style: TextStyle(fontStyle: FontStyle.italic)),
              ),
            const SizedBox(height: 12),
            Wrap(spacing: 8, runSpacing: 8, children: [
              FilledButton(onPressed: () => context.push('/advice/${finding.classId}'), child: const Text('What to do')),
              OutlinedButton(onPressed: () => context.push('/nearby/${referral.code}'), child: Text(referral.action)),
            ]),
          ]),
        ),
      );
    }

    final body = switch (scan.state) {
      VerdictState.problemFound || VerdictState.weakEvidence => [
          if (scan.state == VerdictState.weakEvidence)
            const Card(
              child: ListTile(
                leading: Icon(Icons.info_outline),
                title: Text('Based on few leaves'),
                subtitle: Text('Add more leaves from the same plant for a stronger answer.'),
              ),
            ),
          for (final finding in scan.findings) findingCard(finding),
          if (scan.state == VerdictState.weakEvidence)
            OutlinedButton(
              onPressed: () => context.push('/capture/${scan.crop.name}'),
              child: const Text('Add more leaves'),
            ),
        ],
      VerdictState.healthy => [
          Card(
            child: ListTile(
              leading: const Icon(Icons.check_circle, color: Colors.green, size: 40),
              title: Text('Looks healthy', style: text.titleLarge),
              subtitle: Text('Based on ${scan.acceptedLeaves} leaves. Keep checking your plants regularly.'),
            ),
          ),
          FilledButton(onPressed: () => context.go('/home'), child: const Text('Check another plant')),
        ],
      VerdictState.notSure => [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('We are not sure', style: text.titleLarge),
                const SizedBox(height: 8),
                const BulletList([
                  'The problem may be one this app does not know yet.',
                  'The photos may be unclear.',
                  'Try again with clear photos of 6 leaves in daylight.',
                ]),
              ]),
            ),
          ),
          Wrap(spacing: 8, runSpacing: 8, children: [
            FilledButton(onPressed: () => context.push('/capture/${scan.crop.name}'), child: const Text('Retake photos')),
            OutlinedButton(
              onPressed: () => context.push('/nearby/${PlaceType.extensionOffice.code}'),
              child: const Text('Find help'),
            ),
            const SupportCallButton(),
          ]),
        ],
    };

    return Scaffold(
      appBar: AppBar(title: Text('${scan.crop.label} result')),
      body: Column(children: [
        const DemoBanner(),
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              SizedBox(
                height: 80,
                child: ListView.separated(
                  scrollDirection: Axis.horizontal,
                  itemCount: scan.imagePaths.length,
                  separatorBuilder: (_, _) => const SizedBox(width: 8),
                  itemBuilder: (_, i) => LeafThumb(scan.imagePaths[i], size: 80),
                ),
              ),
              const SizedBox(height: 12),
              ...body,
              const SizedBox(height: 16),
              Text('Checked ${formatDate(scan.createdAt)} · model ${scan.modelVersion}', style: text.bodySmall),
            ],
          ),
        ),
      ]),
    );
  }
}
