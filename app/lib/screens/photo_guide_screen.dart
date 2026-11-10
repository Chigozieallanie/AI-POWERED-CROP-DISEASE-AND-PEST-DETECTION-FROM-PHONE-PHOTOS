import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../domain/models.dart';
import '../providers.dart';

class PhotoGuideScreen extends ConsumerStatefulWidget {
  const PhotoGuideScreen({super.key, required this.crop});
  final Crop crop;

  @override
  ConsumerState<PhotoGuideScreen> createState() => _PhotoGuideScreenState();
}

class _PhotoGuideScreenState extends ConsumerState<PhotoGuideScreen> {
  bool _dontShowAgain = false;

  static const _tips = [
    (Icons.crop_free, 'One leaf fills the photo', 'Get close so the leaf takes up most of the picture.'),
    (Icons.wb_sunny_outlined, 'Use daylight', 'Avoid dark places and strong shadows across the leaf.'),
    (Icons.center_focus_strong, 'Keep it sharp', 'Hold the phone still. Tap the screen to focus.'),
    (Icons.filter_6, 'Up to 6 leaves', 'Photograph up to 6 leaves from the same plant. More leaves gives a better answer.'),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Photo tips: ${widget.crop.label}')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          for (final (icon, title, body) in _tips)
            Card(child: ListTile(leading: Icon(icon, size: 32), title: Text(title), subtitle: Text(body))),
          CheckboxListTile(
            value: _dontShowAgain,
            onChanged: (value) => setState(() => _dontShowAgain = value ?? false),
            title: const Text('Do not show again'),
          ),
          FilledButton(
            onPressed: () async {
              if (_dontShowAgain) await ref.read(settingsProvider.notifier).finishGuide();
              if (context.mounted) context.pushReplacement('/capture/${widget.crop.name}');
            },
            child: const Text('Continue'),
          ),
        ],
      ),
    );
  }
}
