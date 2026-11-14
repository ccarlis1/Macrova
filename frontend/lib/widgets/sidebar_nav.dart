import 'package:flutter/material.dart';

import '../theme/tokens.dart';

/// UI-only nav destination shared by [SidebarNav] and the narrow [NavigationBar].
class AppNavItem {
  const AppNavItem({
    required this.icon,
    required this.selectedIcon,
    required this.label,
  });

  final IconData icon;
  final IconData selectedIcon;
  final String label;
}

abstract final class AppNavItems {
  static const items = [
    AppNavItem(
      icon: Icons.today_outlined,
      selectedIcon: Icons.today,
      label: 'Today',
    ),
    AppNavItem(
      icon: Icons.person_outline,
      selectedIcon: Icons.person,
      label: 'Profile',
    ),
    AppNavItem(
      icon: Icons.egg_outlined,
      selectedIcon: Icons.egg,
      label: 'Ingredients',
    ),
    AppNavItem(
      icon: Icons.build_outlined,
      selectedIcon: Icons.build,
      label: 'Recipe Builder',
    ),
    AppNavItem(
      icon: Icons.menu_book_outlined,
      selectedIcon: Icons.menu_book,
      label: 'Library',
    ),
    AppNavItem(
      icon: Icons.calendar_today_outlined,
      selectedIcon: Icons.calendar_today,
      label: 'Planner',
    ),
    AppNavItem(
      icon: Icons.view_list_outlined,
      selectedIcon: Icons.view_list,
      label: 'Plan View',
    ),
    AppNavItem(
      icon: Icons.smart_toy_outlined,
      selectedIcon: Icons.smart_toy,
      label: 'Agent Pane',
    ),
  ];

  static List<NavigationRailDestination> get railDestinations => items
      .map(
        (item) => NavigationRailDestination(
          icon: Icon(item.icon),
          selectedIcon: Icon(item.selectedIcon),
          label: Text(item.label),
        ),
      )
      .toList();

  static List<NavigationDestination> get navigationDestinations => items
      .map(
        (item) => NavigationDestination(
          icon: Icon(item.icon),
          selectedIcon: Icon(item.selectedIcon),
          label: item.label,
        ),
      )
      .toList();
}

class SidebarNav extends StatelessWidget {
  final int selectedIndex;
  final ValueChanged<int> onDestinationSelected;

  const SidebarNav({
    super.key,
    required this.selectedIndex,
    required this.onDestinationSelected,
  });

  @override
  Widget build(BuildContext context) {
    final tokens =
        Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;

    return NavigationRail(
      selectedIndex: selectedIndex,
      onDestinationSelected: onDestinationSelected,
      labelType: NavigationRailLabelType.all,
      leading: Padding(
        padding: const EdgeInsets.symmetric(vertical: MacrovaSpacing.sm),
        child: Text(
          'Macrova',
          style: MacrovaTypography.subtitle(tokens.accent),
        ),
      ),
      destinations: AppNavItems.railDestinations,
    );
  }
}
