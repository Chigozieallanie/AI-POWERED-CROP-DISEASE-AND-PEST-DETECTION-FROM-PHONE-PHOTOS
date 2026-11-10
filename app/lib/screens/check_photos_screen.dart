import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../domain/models.dart';
import '../providers.dart';
import '../widgets/common.dart';
import 'capture_screen.dart';

class CheckPhotosScreen extends ConsumerStatefulWidget {
  const CheckPhotosScreen({super.key, required this.session});
  final CaptureSession session;

  @override
  ConsumerState<CheckPhotosScreen> createState() => _CheckPhotosScreenState();
}

class _CheckPhotosScreenState extends ConsumerState<CheckPhotosScreen> {
  final Map<String, PhotoStatus> _status = {};
  bool _analysing = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _run();
  }

  Future<void> _run() async {
    final service = ref.read(diagnosisProvider);
    try {
      for (final path in widget.session.paths) {
        final check = await service.checkPhoto(widget.session.crop, path);
        if (!mounted) return;
        setState(() => _status[path] = check.status);
      }
      final accepted = [for (final p in widget.session.paths) if (_status[p] == PhotoStatus.accepted) p];
      if (accepted.isEmpty) return;
      setState(() => _analysing = true);
      final result = await service.diagnose(widget.session.crop, accepted);
      ref.read(scansProvider.notifier).add(result);
      if (mounted) context.pushReplacement('/result/${result.id}');
    } catch (error) {
      if (mounted) setState(() => _error = 'The photos could not be checked. Try again.');
    }
  }

  @override
  Widget build(BuildContext context) {
    final paths = widget.session.paths;
    final done = _status.length == paths.length;
    final allRejected = done && !_status.values.contains(PhotoStatus.accepted);
    return Scaffold(
      appBar: AppBar(title: const Text('Checking photos')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          for (final path in paths)
            Card(
              child: ListTile(
                leading: LeafThumb(path, size: 56),
                title: Text(_status[path]?.message ?? 'Checking...'),
                trailing: switch (_status[path]) {
                  null => const SizedBox(width: 24, height: 24, child: CircularProgressIndicator(strokeWidth: 2)),
                  PhotoStatus.accepted => const Icon(Icons.check_circle, color: Colors.green),
                  _ => const Icon(Icons.error_outline, color: Colors.orange),
                },
              ),
            ),
          const SizedBox(height: 16),
          if (_error != null) Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
          if (_analysing) const Column(children: [LinearProgressIndicator(), SizedBox(height: 8), Text('Analysing the plant...')]),
          if (allRejected) ...[
            const Text('None of the photos could be used. Please retake them.'),
            const SizedBox(height: 12),
            FilledButton(
              onPressed: () => context.pushReplacement('/capture/${widget.session.crop.name}'),
              child: const Text('Retake photos'),
            ),
          ],
        ],
      ),
    );
  }
}
