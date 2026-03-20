import 'package:flutter/material.dart';

import '../models/models.dart';
import '../services/api_service.dart';

class ProfileSetupScreen extends StatefulWidget {
  const ProfileSetupScreen({super.key});

  @override
  State<ProfileSetupScreen> createState() => _ProfileSetupScreenState();
}

class _ProfileSetupScreenState extends State<ProfileSetupScreen> {
  final _formKey = GlobalKey<FormState>();

  final _dailyCaloriesController = TextEditingController();
  final _dailyProteinController = TextEditingController();
  final _dailyFatMinController = TextEditingController();
  final _dailyFatMaxController = TextEditingController();

  final _likedFoodsController = TextEditingController();
  final _dislikedFoodsController = TextEditingController();
  final _allergiesController = TextEditingController();

  TimeOfDay _breakfastTime = const TimeOfDay(hour: 8, minute: 0);
  TimeOfDay _lunchTime = const TimeOfDay(hour: 12, minute: 0);
  TimeOfDay _dinnerTime = const TimeOfDay(hour: 18, minute: 0);
  int _breakfastBusyness = 2;
  int _lunchBusyness = 3;
  int _dinnerBusyness = 4;

  bool _hasWorkout = false;
  TimeOfDay _workoutTime = const TimeOfDay(hour: 17, minute: 0);

  @override
  void dispose() {
    _dailyCaloriesController.dispose();
    _dailyProteinController.dispose();
    _dailyFatMinController.dispose();
    _dailyFatMaxController.dispose();
    _likedFoodsController.dispose();
    _dislikedFoodsController.dispose();
    _allergiesController.dispose();
    super.dispose();
  }

  String _toHhMm(TimeOfDay time) {
    final hh = time.hour.toString().padLeft(2, '0');
    final mm = time.minute.toString().padLeft(2, '0');
    return '$hh:$mm';
  }

  List<String> _csvToList(String text) {
    return text
        .split(',')
        .map((item) => item.trim())
        .where((item) => item.isNotEmpty)
        .toList();
  }

  Future<void> _pickTime(
    BuildContext context, {
    required TimeOfDay initial,
    required ValueChanged<TimeOfDay> onSelected,
  }) async {
    final picked = await showTimePicker(
      context: context,
      initialTime: initial,
    );
    if (picked != null) {
      setState(() => onSelected(picked));
    }
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    final fatMin = double.parse(_dailyFatMinController.text.trim());
    final fatMax = double.parse(_dailyFatMaxController.text.trim());
    if (fatMax < fatMin) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Fat max must be greater than or equal to fat min.')),
      );
      return;
    }

    final schedule = <String, int>{
      _toHhMm(_breakfastTime): _breakfastBusyness,
      _toHhMm(_lunchTime): _lunchBusyness,
      _toHhMm(_dinnerTime): _dinnerBusyness,
      if (_hasWorkout) _toHhMm(_workoutTime): 0,
    };

    final request = PlanRequest(
      dailyCalories: int.parse(_dailyCaloriesController.text.trim()),
      dailyProteinG: double.parse(_dailyProteinController.text.trim()),
      dailyFatGMin: fatMin,
      dailyFatGMax: fatMax,
      schedule: schedule,
      likedFoods: _csvToList(_likedFoodsController.text),
      dislikedFoods: _csvToList(_dislikedFoodsController.text),
      allergies: _csvToList(_allergiesController.text),
      days: 1,
      ingredientSource: 'local',
      planningMode: 'deterministic',
    );

    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (_) => const Center(child: CircularProgressIndicator()),
    );

    try {
      final mealPlan = await ApiService.generatePlan(request);
      if (!mounted) {
        return;
      }
      Navigator.of(context).pop();
      Navigator.pushNamed(context, '/plan', arguments: mealPlan);
    } catch (e) {
      if (!mounted) {
        return;
      }
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          backgroundColor: Theme.of(context).colorScheme.errorContainer,
          content: Text(
            'API failed: $e',
            style: TextStyle(color: Theme.of(context).colorScheme.onErrorContainer),
          ),
        ),
      );
    }
  }

  String? _requiredNumber(String? value, {bool allowDecimal = true}) {
    if (value == null || value.trim().isEmpty) {
      return 'Required';
    }
    final text = value.trim();
    final number = allowDecimal ? double.tryParse(text) : int.tryParse(text);
    if (number == null) {
      return allowDecimal ? 'Enter a valid number' : 'Enter a valid integer';
    }
    return null;
  }

  String _busynessLabel(int value) {
    switch (value) {
      case 1:
        return '1 - Snack / 5 min';
      case 2:
        return '2 - 15 min';
      case 3:
        return '3 - 30 min';
      default:
        return '4 - 45+ min';
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Profile'),
      ),
      body: LayoutBuilder(
        builder: (context, constraints) {
          final maxWidth = constraints.maxWidth > 560 ? 560.0 : double.infinity;
          return SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Center(
              child: ConstrainedBox(
                constraints: BoxConstraints(maxWidth: maxWidth),
                child: Form(
                  key: _formKey,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Nutrition Goals',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const SizedBox(height: 12),
                      TextFormField(
                        controller: _dailyCaloriesController,
                        decoration: const InputDecoration(
                          labelText: 'Daily Calories',
                          border: OutlineInputBorder(),
                        ),
                        keyboardType: const TextInputType.numberWithOptions(decimal: false),
                        validator: (value) => _requiredNumber(value, allowDecimal: false),
                      ),
                      const SizedBox(height: 12),
                      TextFormField(
                        controller: _dailyProteinController,
                        decoration: const InputDecoration(
                          labelText: 'Daily Protein (g)',
                          border: OutlineInputBorder(),
                        ),
                        keyboardType: const TextInputType.numberWithOptions(decimal: true),
                        validator: _requiredNumber,
                      ),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          Expanded(
                            child: TextFormField(
                              controller: _dailyFatMinController,
                              decoration: const InputDecoration(
                                labelText: 'Fat Min (g)',
                                border: OutlineInputBorder(),
                              ),
                              keyboardType:
                                  const TextInputType.numberWithOptions(decimal: true),
                              validator: _requiredNumber,
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: TextFormField(
                              controller: _dailyFatMaxController,
                              decoration: const InputDecoration(
                                labelText: 'Fat Max (g)',
                                border: OutlineInputBorder(),
                              ),
                              keyboardType:
                                  const TextInputType.numberWithOptions(decimal: true),
                              validator: _requiredNumber,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 24),
                      Text(
                        'Schedule',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const SizedBox(height: 12),
                      _buildMealScheduleCard(
                        title: 'Breakfast',
                        time: _breakfastTime,
                        busyness: _breakfastBusyness,
                        onPickTime: () => _pickTime(
                          context,
                          initial: _breakfastTime,
                          onSelected: (t) => _breakfastTime = t,
                        ),
                        onBusynessChanged: (value) =>
                            setState(() => _breakfastBusyness = value),
                      ),
                      const SizedBox(height: 8),
                      _buildMealScheduleCard(
                        title: 'Lunch',
                        time: _lunchTime,
                        busyness: _lunchBusyness,
                        onPickTime: () => _pickTime(
                          context,
                          initial: _lunchTime,
                          onSelected: (t) => _lunchTime = t,
                        ),
                        onBusynessChanged: (value) =>
                            setState(() => _lunchBusyness = value),
                      ),
                      const SizedBox(height: 8),
                      _buildMealScheduleCard(
                        title: 'Dinner',
                        time: _dinnerTime,
                        busyness: _dinnerBusyness,
                        onPickTime: () => _pickTime(
                          context,
                          initial: _dinnerTime,
                          onSelected: (t) => _dinnerTime = t,
                        ),
                        onBusynessChanged: (value) =>
                            setState(() => _dinnerBusyness = value),
                      ),
                      const SizedBox(height: 8),
                      CheckboxListTile(
                        contentPadding: EdgeInsets.zero,
                        title: const Text('Workout?'),
                        value: _hasWorkout,
                        onChanged: (value) =>
                            setState(() => _hasWorkout = value ?? false),
                      ),
                      if (_hasWorkout)
                        ListTile(
                          contentPadding: EdgeInsets.zero,
                          shape: RoundedRectangleBorder(
                            side: BorderSide(color: colorScheme.outlineVariant),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          title: const Text('Workout Time'),
                          subtitle: Text(_toHhMm(_workoutTime)),
                          trailing: const Icon(Icons.access_time),
                          onTap: () => _pickTime(
                            context,
                            initial: _workoutTime,
                            onSelected: (t) => _workoutTime = t,
                          ),
                        ),
                      const SizedBox(height: 24),
                      Text(
                        'Preferences',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const SizedBox(height: 12),
                      TextFormField(
                        controller: _likedFoodsController,
                        decoration: const InputDecoration(
                          labelText: 'Liked Foods (comma-separated)',
                          border: OutlineInputBorder(),
                        ),
                      ),
                      const SizedBox(height: 12),
                      TextFormField(
                        controller: _dislikedFoodsController,
                        decoration: const InputDecoration(
                          labelText: 'Disliked Foods (comma-separated)',
                          border: OutlineInputBorder(),
                        ),
                      ),
                      const SizedBox(height: 12),
                      TextFormField(
                        controller: _allergiesController,
                        decoration: const InputDecoration(
                          labelText: 'Allergies (comma-separated)',
                          border: OutlineInputBorder(),
                        ),
                      ),
                      const SizedBox(height: 20),
                      SizedBox(
                        width: double.infinity,
                        child: ElevatedButton(
                          onPressed: _submit,
                          child: const Text('Generate Plan'),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildMealScheduleCard({
    required String title,
    required TimeOfDay time,
    required int busyness,
    required VoidCallback onPickTime,
    required ValueChanged<int> onBusynessChanged,
  }) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            ListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Time'),
              subtitle: Text(_toHhMm(time)),
              trailing: const Icon(Icons.access_time),
              onTap: onPickTime,
            ),
            DropdownButtonFormField<int>(
              initialValue: busyness,
              decoration: const InputDecoration(
                labelText: 'Busyness',
                border: OutlineInputBorder(),
              ),
              items: [1, 2, 3, 4]
                  .map(
                    (value) => DropdownMenuItem<int>(
                      value: value,
                      child: Text(_busynessLabel(value)),
                    ),
                  )
                  .toList(),
              onChanged: (value) {
                if (value != null) {
                  onBusynessChanged(value);
                }
              },
            ),
          ],
        ),
      ),
    );
  }
}
