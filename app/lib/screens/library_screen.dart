import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../domain/models.dart';
import '../providers.dart';

class LibraryScreen extends ConsumerWidget {
  const LibraryScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final content = ref.watch(contentProvider);
    return DefaultTabController(
      length: Crop.values.length,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Disease and pest library'),
          bottom: TabBar(tabs: [for (final crop in Crop.values) Tab(text: crop.label)]),
        ),
        body: TabBarView(children: [
          for (final crop in Crop.values)
            ListView(padding: const EdgeInsets.all(12), children: [
              for (final problem in content.library(crop))
                Card(
                  child: ListTile(
                    leading: Icon(problem.kind == ClassKind.pest ? Icons.bug_report_outlined : Icons.coronavirus_outlined),
                    title: Text(problem.name),
                    subtitle: Text(problem.kind == ClassKind.pest ? 'Pest' : 'Disease'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => context.push('/advice/${problem.id}'),
                  ),
                ),
            ]),
        ]),
      ),
    );
  }
}
