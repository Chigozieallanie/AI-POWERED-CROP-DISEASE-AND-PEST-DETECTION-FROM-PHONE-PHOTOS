import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../domain/models.dart';
import '../providers.dart';
import '../widgets/common.dart';

class HistoryScreen extends ConsumerStatefulWidget {
  const HistoryScreen({super.key});

  @override
  ConsumerState<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends ConsumerState<HistoryScreen> {
  Crop? _crop;

  @override
  Widget build(BuildContext context) {
    final scans = ref.watch(scansProvider).where((s) => _crop == null || s.crop == _crop).toList();
    return Scaffold(
      appBar: AppBar(
        title: const Text('History'),
        actions: [
          if (ref.watch(scansProvider).isNotEmpty)
            IconButton(
              tooltip: 'Delete all',
              icon: const Icon(Icons.delete_sweep_outlined),
              onPressed: () async {
                final ok = await confirmDelete(context, 'Delete all checks?');
                if (ok) ref.read(scansProvider.notifier).deleteAll();
              },
            ),
        ],
      ),
      body: Column(children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: Wrap(spacing: 8, children: [
            ChoiceChip(label: const Text('All'), selected: _crop == null, onSelected: (_) => setState(() => _crop = null)),
            for (final crop in Crop.values)
              ChoiceChip(label: Text(crop.label), selected: _crop == crop, onSelected: (_) => setState(() => _crop = crop)),
          ]),
        ),
        Expanded(
          child: scans.isEmpty
              ? const Center(child: Text('No checks yet.'))
              : ListView(padding: const EdgeInsets.symmetric(horizontal: 12), children: [
                  for (final scan in scans)
                    Dismissible(
                      key: ValueKey(scan.id),
                      direction: DismissDirection.endToStart,
                      background: Container(
                        alignment: Alignment.centerRight,
                        padding: const EdgeInsets.only(right: 16),
                        color: Theme.of(context).colorScheme.errorContainer,
                        child: const Icon(Icons.delete_outline),
                      ),
                      onDismissed: (_) => ref.read(scansProvider.notifier).delete(scan.id),
                      child: ScanTile(scan: scan),
                    ),
                ]),
        ),
      ]),
    );
  }
}

class ScanTile extends ConsumerWidget {
  const ScanTile({super.key, required this.scan});
  final PlantResult scan;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final content = ref.watch(contentProvider);
    final summary = switch (scan.state) {
      VerdictState.healthy => 'Looks healthy',
      VerdictState.notSure => 'Not sure',
      _ => scan.findings.map((f) => content.problemClass(f.classId)?.name ?? f.classId).join(', '),
    };
    return Card(
      child: ListTile(
        leading: scan.imagePaths.isEmpty ? null : LeafThumb(scan.imagePaths.first, size: 48),
        title: Text(summary),
        subtitle: Text('${scan.crop.label} · ${formatDate(scan.createdAt)}'),
        trailing: const Icon(Icons.chevron_right),
        onTap: () => context.push('/result/${scan.id}'),
      ),
    );
  }
}

Future<bool> confirmDelete(BuildContext context, String title) async =>
    await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(title),
        content: const Text('This cannot be undone.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Delete')),
        ],
      ),
    ) ??
    false;
