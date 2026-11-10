import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../domain/models.dart';
import '../providers.dart';
import '../widgets/common.dart';

class AdviceScreen extends ConsumerWidget {
  const AdviceScreen({super.key, required this.classId});
  final String classId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final content = ref.watch(contentProvider);
    final problem = content.problemClass(classId);
    final advice = content.advice(classId);
    final referral = problem?.referralType ?? PlaceType.extensionOffice;
    final text = Theme.of(context).textTheme;

    return Scaffold(
      appBar: AppBar(title: Text(problem?.name ?? 'What to do')),
      body: Column(children: [
        const DemoBanner(),
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              if (advice == null)
                const Text('Advice for this problem is not available. Ask your nearest extension office.')
              else ...[
                if (advice.stepsNow.isNotEmpty) ...[
                  const SectionTitle('Do this now'),
                  BulletList(advice.stepsNow, numbered: true),
                ],
                if (advice.prevention.isNotEmpty) ...[
                  const SectionTitle('Prevent it next season'),
                  BulletList(advice.prevention),
                ],
                if (advice.doNot.isNotEmpty) ...[
                  const SectionTitle('Do not'),
                  BulletList(advice.doNot),
                ],
                if (advice.safety.isNotEmpty)
                  Card(
                    color: Theme.of(context).colorScheme.errorContainer,
                    margin: const EdgeInsets.only(top: 20),
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Row(children: [
                          const Icon(Icons.health_and_safety),
                          const SizedBox(width: 8),
                          Text('Safety', style: text.titleMedium),
                        ]),
                        const SizedBox(height: 8),
                        BulletList(advice.safety),
                      ]),
                    ),
                  ),
                const SizedBox(height: 16),
                Text(
                  advice.reviewed ? 'Reviewed by ${advice.reviewer ?? 'an agronomist'}' : 'Not yet reviewed by an agronomist',
                  style: text.bodySmall,
                ),
              ],
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: () => context.push('/nearby/${referral.code}'),
                icon: const Icon(Icons.place),
                label: Text(referral.action),
              ),
            ],
          ),
        ),
      ]),
    );
  }
}
