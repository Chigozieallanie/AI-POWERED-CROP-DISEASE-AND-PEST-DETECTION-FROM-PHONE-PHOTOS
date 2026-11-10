import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';

import '../domain/models.dart';
import '../widgets/common.dart';

const maxLeaves = 6;

class CaptureSession {
  CaptureSession(this.crop, this.paths);
  final Crop crop;
  final List<String> paths;
}

class CaptureScreen extends StatefulWidget {
  const CaptureScreen({super.key, required this.crop, this.initialPaths = const []});
  final Crop crop;
  final List<String> initialPaths;

  @override
  State<CaptureScreen> createState() => _CaptureScreenState();
}

class _CaptureScreenState extends State<CaptureScreen> {
  final _picker = ImagePicker();
  late final List<String> _paths = [...widget.initialPaths];

  Future<void> _add(ImageSource source) async {
    try {
      if (source == ImageSource.gallery) {
        final files = await _picker.pickMultiImage(limit: maxLeaves - _paths.length, imageQuality: 90);
        setState(() => _paths.addAll(files.take(maxLeaves - _paths.length).map((f) => f.path)));
      } else {
        final file = await _picker.pickImage(source: source, imageQuality: 90, maxWidth: 1600);
        if (file != null) setState(() => _paths.add(file.path));
      }
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('The camera could not open. Check camera permission in phone settings.')),
      );
    }
  }

  Future<void> _check() async {
    if (_paths.length < 3) {
      final proceed = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Fewer than 3 leaves'),
          content: const Text('The answer will be weaker. Add more leaves from the same plant for a better answer.'),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Add more')),
            FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Check anyway')),
          ],
        ),
      );
      if (proceed != true) return;
    }
    if (mounted) context.push('/check', extra: CaptureSession(widget.crop, List.of(_paths)));
  }

  @override
  Widget build(BuildContext context) {
    final full = _paths.length >= maxLeaves;
    final text = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(title: Text('${widget.crop.label}: photograph leaves')),
      body: Column(children: [
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Text(full ? 'All $maxLeaves leaves taken' : 'Leaf ${_paths.length + 1} of $maxLeaves', style: text.headlineSmall),
              const SizedBox(height: 4),
              const Text('Use leaves from the same plant. Let one leaf fill the photo.'),
              const SizedBox(height: 16),
              Wrap(spacing: 8, runSpacing: 8, children: [
                for (var i = 0; i < _paths.length; i++)
                  Stack(children: [
                    LeafThumb(_paths[i], size: 96),
                    Positioned(
                      right: 0,
                      top: 0,
                      child: IconButton.filledTonal(
                        visualDensity: VisualDensity.compact,
                        tooltip: 'Remove',
                        onPressed: () => setState(() => _paths.removeAt(i)),
                        icon: const Icon(Icons.close, size: 16),
                      ),
                    ),
                  ]),
              ]),
            ],
          ),
        ),
        SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(children: [
              Row(children: [
                Expanded(
                  child: FilledButton.icon(
                    onPressed: full ? null : () => _add(ImageSource.camera),
                    icon: const Icon(Icons.photo_camera),
                    label: const Text('Take photo'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: full ? null : () => _add(ImageSource.gallery),
                    icon: const Icon(Icons.photo_library_outlined),
                    label: const Text('From gallery'),
                  ),
                ),
              ]),
              const SizedBox(height: 8),
              SizedBox(
                width: double.infinity,
                child: FilledButton.tonal(
                  onPressed: _paths.isEmpty ? null : _check,
                  child: Text('Check plant (${_paths.length} ${_paths.length == 1 ? 'leaf' : 'leaves'})'),
                ),
              ),
            ]),
          ),
        ),
      ]),
    );
  }
}
