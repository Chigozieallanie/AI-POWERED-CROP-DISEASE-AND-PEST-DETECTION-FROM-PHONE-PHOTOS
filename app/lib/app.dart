import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'domain/models.dart';
import 'providers.dart';
import 'screens/advice_screen.dart';
import 'screens/capture_screen.dart';
import 'screens/check_photos_screen.dart';
import 'screens/history_screen.dart';
import 'screens/home_screen.dart';
import 'screens/library_screen.dart';
import 'screens/nearby_screen.dart';
import 'screens/photo_guide_screen.dart';
import 'screens/place_screen.dart';
import 'screens/result_screen.dart';
import 'screens/settings_screen.dart';
import 'screens/welcome_screen.dart';

final routerProvider = Provider<GoRouter>((ref) {
  final settings = ref.read(settingsProvider.notifier);
  return GoRouter(
    initialLocation: '/home',
    redirect: (context, state) =>
        !settings.welcomeDone && state.matchedLocation != '/welcome' ? '/welcome' : null,
    routes: [
      GoRoute(path: '/welcome', builder: (_, _) => const WelcomeScreen()),
      StatefulShellRoute.indexedStack(
        builder: (context, state, shell) => _TabScaffold(shell: shell),
        branches: [
          StatefulShellBranch(routes: [GoRoute(path: '/home', builder: (_, _) => const HomeScreen())]),
          StatefulShellBranch(routes: [GoRoute(path: '/history', builder: (_, _) => const HistoryScreen())]),
          StatefulShellBranch(routes: [GoRoute(path: '/library', builder: (_, _) => const LibraryScreen())]),
          StatefulShellBranch(routes: [GoRoute(path: '/help', builder: (_, _) => const NearbyScreen())]),
        ],
      ),
      GoRoute(
        path: '/guide/:crop',
        builder: (_, state) => PhotoGuideScreen(crop: Crop.values.byName(state.pathParameters['crop']!)),
      ),
      GoRoute(
        path: '/capture/:crop',
        builder: (_, state) => CaptureScreen(crop: Crop.values.byName(state.pathParameters['crop']!)),
      ),
      GoRoute(
        path: '/check',
        builder: (_, state) => CheckPhotosScreen(session: state.extra! as CaptureSession),
      ),
      GoRoute(path: '/result/:id', builder: (_, state) => ResultScreen(scanId: state.pathParameters['id']!)),
      GoRoute(path: '/advice/:classId', builder: (_, state) => AdviceScreen(classId: state.pathParameters['classId']!)),
      GoRoute(
        path: '/nearby/:type',
        builder: (_, state) => NearbyScreen(initialType: PlaceType.fromCode(state.pathParameters['type'])),
      ),
      GoRoute(path: '/place/:id', builder: (_, state) => PlaceScreen(placeId: int.parse(state.pathParameters['id']!))),
      GoRoute(path: '/settings', builder: (_, _) => const SettingsScreen()),
    ],
  );
});

class CropCheckApp extends ConsumerWidget {
  const CropCheckApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    ThemeData theme(Brightness brightness) => ThemeData(
          colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF2E7D32), brightness: brightness),
          useMaterial3: true,
          visualDensity: VisualDensity.standard,
        );
    return MaterialApp.router(
      title: 'Crop Check',
      theme: theme(Brightness.light),
      darkTheme: theme(Brightness.dark),
      routerConfig: ref.watch(routerProvider),
    );
  }
}

class _TabScaffold extends StatelessWidget {
  const _TabScaffold({required this.shell});
  final StatefulNavigationShell shell;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: shell,
      bottomNavigationBar: NavigationBar(
        selectedIndex: shell.currentIndex,
        onDestinationSelected: (index) => shell.goBranch(index, initialLocation: index == shell.currentIndex),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.home_outlined), selectedIcon: Icon(Icons.home), label: 'Home'),
          NavigationDestination(icon: Icon(Icons.history), label: 'History'),
          NavigationDestination(icon: Icon(Icons.menu_book_outlined), selectedIcon: Icon(Icons.menu_book), label: 'Library'),
          NavigationDestination(icon: Icon(Icons.place_outlined), selectedIcon: Icon(Icons.place), label: 'Help'),
        ],
      ),
    );
  }
}
