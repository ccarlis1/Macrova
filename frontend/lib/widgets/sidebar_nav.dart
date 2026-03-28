import 'package:flutter/material.dart';

class SidebarNav extends StatelessWidget {
  final int selectedIndex;
  final ValueChanged<int> onDestinationSelected;

  const SidebarNav({
    super.key,
    required this.selectedIndex,
    required this.onDestinationSelected,
  });

  static const destinations = [
    NavigationRailDestination(
      icon: Icon(Icons.person_outline),
      selectedIcon: Icon(Icons.person),
      label: Text('Profile'),
    ),
    NavigationRailDestination(
      icon: Icon(Icons.egg_outlined),
      selectedIcon: Icon(Icons.egg),
      label: Text('Ingredients'),
    ),
    NavigationRailDestination(
      icon: Icon(Icons.build_outlined),
      selectedIcon: Icon(Icons.build),
      label: Text('Recipe Builder'),
    ),
    NavigationRailDestination(
      icon: Icon(Icons.menu_book_outlined),
      selectedIcon: Icon(Icons.menu_book),
      label: Text('Library'),
    ),
    NavigationRailDestination(
      icon: Icon(Icons.calendar_today_outlined),
      selectedIcon: Icon(Icons.calendar_today),
      label: Text('Planner'),
    ),
    NavigationRailDestination(
      icon: Icon(Icons.view_list_outlined),
      selectedIcon: Icon(Icons.view_list),
      label: Text('Plan View'),
    ),
    NavigationRailDestination(
      icon: Icon(Icons.smart_toy_outlined),
      selectedIcon: Icon(Icons.smart_toy),
      label: Text('Agent Pane'),
    ),
  ];

  @override
  Widget build(BuildContext context) {
    return NavigationRail(
      selectedIndex: selectedIndex,
      onDestinationSelected: onDestinationSelected,
      labelType: NavigationRailLabelType.all,
      leading: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Text(
          'Macrova',
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.bold,
                color: Theme.of(context).colorScheme.primary,
              ),
        ),
      ),
      destinations: destinations,
    );
  }
}
