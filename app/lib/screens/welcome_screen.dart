import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../providers.dart';

class WelcomeScreen extends ConsumerStatefulWidget {
  const WelcomeScreen({super.key});

  @override
  ConsumerState<WelcomeScreen> createState() => _WelcomeScreenState();
}

class _WelcomeScreenState extends ConsumerState<WelcomeScreen> {
  bool _sharePhotos = false;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(24),
          children: [
            Icon(Icons.eco, size: 64, color: Theme.of(context).colorScheme.primary),
            const SizedBox(height: 16),
            Text('Crop Check', style: text.headlineMedium, textAlign: TextAlign.center),
            const SizedBox(height: 8),
            Text(
              'Take photos of cassava or maize leaves. Find out what the problem may be, what to do, '
              'and where to get help. Works without internet.',
              style: text.bodyLarge,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 24),
            Card(
              child: ListTile(
                leading: const Icon(Icons.warning_amber),
                title: const Text('This app can be wrong'),
                subtitle: const Text('It does not replace an extension officer.'),
              ),
            ),
            const ListTile(
              leading: Icon(Icons.language),
              title: Text('Language'),
              trailing: Text('English'),
            ),
            const ListTile(
              leading: Icon(Icons.photo_camera_outlined),
              title: Text('Camera'),
              subtitle: Text('Used to photograph leaves. Photos stay on your phone.'),
            ),
            const ListTile(
              leading: Icon(Icons.location_on_outlined),
              title: Text('Location'),
              subtitle: Text('Used to find the nearest help. It stays on your phone.'),
            ),
            SwitchListTile(
              value: _sharePhotos,
              onChanged: (value) => setState(() => _sharePhotos = value),
              title: const Text('Help improve the app by sharing photos'),
              subtitle: const Text('Off by default. You can change this later in Settings.'),
            ),
            const SizedBox(height: 16),
            FilledButton(
              onPressed: () async {
                await ref.read(settingsProvider.notifier).finishWelcome(sharePhotos: _sharePhotos);
                if (context.mounted) context.go('/home');
              },
              child: const Text('Continue'),
            ),
          ],
        ),
      ),
    );
  }
}
