import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers.dart';
import 'history_screen.dart';

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final sharing = ref.watch(settingsProvider);
    final engine = ref.watch(diagnosisProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(children: [
        const ListTile(leading: Icon(Icons.language), title: Text('Language'), trailing: Text('English')),
        SwitchListTile(
          secondary: const Icon(Icons.photo_outlined),
          title: const Text('Share photos to improve the app'),
          subtitle: const Text('Location is removed before any photo is sent.'),
          value: sharing,
          onChanged: (value) => ref.read(settingsProvider.notifier).setSharing(value),
        ),
        ListTile(
          leading: const Icon(Icons.system_update_outlined),
          title: const Text('Check for updates'),
          subtitle: Text(engine.isDemo ? 'Models: demo' : 'Models installed'),
          onTap: () => ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Updates will be available when the server is online.')),
          ),
        ),
        ListTile(
          leading: const Icon(Icons.delete_outline),
          title: const Text('Delete all my data'),
          onTap: () async {
            if (await confirmDelete(context, 'Delete all your checks and photos?')) {
              ref.read(scansProvider.notifier).deleteAll();
            }
          },
        ),
        const AboutListTile(
          icon: Icon(Icons.info_outline),
          applicationName: 'Crop Check',
          applicationVersion: '0.1.0',
          aboutBoxChildren: [
            Text('This app can be wrong. It does not replace an extension officer. '
                'Photos and location stay on your phone unless you choose to share photos.'),
          ],
        ),
      ]),
    );
  }
}
