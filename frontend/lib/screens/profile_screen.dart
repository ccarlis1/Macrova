import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/user_profile.dart';
import '../providers/profile_provider.dart';
import '../widgets/section_header.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  final _formKey = GlobalKey<FormState>();

  // Macro ratios
  final _proteinPctCtrl = TextEditingController();
  final _carbsPctCtrl = TextEditingController();
  final _fatPctCtrl = TextEditingController();
  final _totalCaloriesCtrl = TextEditingController();

  // Manual macro inputs
  final _caloriesCtrl = TextEditingController();
  final _proteinGCtrl = TextEditingController();
  final _carbsGCtrl = TextEditingController();
  final _fatGCtrl = TextEditingController();

  // Micronutrient goals
  final _vitaminACtrl = TextEditingController();
  final _vitaminCCtrl = TextEditingController();
  final _ironCtrl = TextEditingController();
  final _calciumCtrl = TextEditingController();
  final _fiberCtrl = TextEditingController();
  final _sodiumCtrl = TextEditingController();

  // API keys
  final _ingredientApiKeyCtrl = TextEditingController();
  final _llmApiKeyCtrl = TextEditingController();

  // Allergy input
  final _allergyCtrl = TextEditingController();

  bool _calorieDeficitMode = false;
  String _demographicGroup = '';
  List<String> _allergies = [];

  bool _initialized = false;

  static const _demographicOptions = [
    '',
    'adult_male',
    'adult_female',
    'teen_male',
    'teen_female',
    'child',
    'pregnancy',
    'lactation',
    'elderly_male',
    'elderly_female',
  ];

  static const _demographicLabels = {
    '': 'Select demographic...',
    'adult_male': 'Adult Male (19-50)',
    'adult_female': 'Adult Female (19-50)',
    'teen_male': 'Teen Male (14-18)',
    'teen_female': 'Teen Female (14-18)',
    'child': 'Child (9-13)',
    'pregnancy': 'Pregnancy',
    'lactation': 'Lactation',
    'elderly_male': 'Elderly Male (51+)',
    'elderly_female': 'Elderly Female (51+)',
  };

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_initialized) {
      _loadFromProvider();
      _initialized = true;
    }
  }

  void _loadFromProvider() {
    final profile = context.read<ProfileProvider>().profile;
    _proteinPctCtrl.text = profile.proteinPct.toStringAsFixed(0);
    _carbsPctCtrl.text = profile.carbsPct.toStringAsFixed(0);
    _fatPctCtrl.text = profile.fatPct.toStringAsFixed(0);
    _totalCaloriesCtrl.text = profile.calories.toStringAsFixed(0);
    _caloriesCtrl.text = profile.calories.toStringAsFixed(0);
    _proteinGCtrl.text = profile.proteinG.toStringAsFixed(0);
    _carbsGCtrl.text = profile.carbsG.toStringAsFixed(0);
    _fatGCtrl.text = profile.fatG.toStringAsFixed(0);
    _vitaminACtrl.text = _nonZero(profile.micronutrientGoals.vitaminAUg);
    _vitaminCCtrl.text = _nonZero(profile.micronutrientGoals.vitaminCMg);
    _ironCtrl.text = _nonZero(profile.micronutrientGoals.ironMg);
    _calciumCtrl.text = _nonZero(profile.micronutrientGoals.calciumMg);
    _fiberCtrl.text = _nonZero(profile.micronutrientGoals.fiberG);
    _sodiumCtrl.text = _nonZero(profile.micronutrientGoals.sodiumMg);
    _ingredientApiKeyCtrl.text = profile.ingredientApiKey;
    _llmApiKeyCtrl.text = profile.llmApiKey;
    _calorieDeficitMode = profile.calorieDeficitMode;
    _demographicGroup = profile.demographicGroup;
    _allergies = List.from(profile.allergies);
  }

  String _nonZero(double v) => v > 0 ? v.toStringAsFixed(0) : '';

  @override
  void dispose() {
    _proteinPctCtrl.dispose();
    _carbsPctCtrl.dispose();
    _fatPctCtrl.dispose();
    _totalCaloriesCtrl.dispose();
    _caloriesCtrl.dispose();
    _proteinGCtrl.dispose();
    _carbsGCtrl.dispose();
    _fatGCtrl.dispose();
    _vitaminACtrl.dispose();
    _vitaminCCtrl.dispose();
    _ironCtrl.dispose();
    _calciumCtrl.dispose();
    _fiberCtrl.dispose();
    _sodiumCtrl.dispose();
    _ingredientApiKeyCtrl.dispose();
    _llmApiKeyCtrl.dispose();
    _allergyCtrl.dispose();
    super.dispose();
  }

  void _calculateFromRatios() {
    final calories = double.tryParse(_totalCaloriesCtrl.text.trim()) ?? 0;
    final pPct = double.tryParse(_proteinPctCtrl.text.trim()) ?? 0;
    final cPct = double.tryParse(_carbsPctCtrl.text.trim()) ?? 0;
    final fPct = double.tryParse(_fatPctCtrl.text.trim()) ?? 0;

    setState(() {
      _caloriesCtrl.text = calories.toStringAsFixed(0);
      _proteinGCtrl.text = (calories * pPct / 100 / 4).toStringAsFixed(0);
      _carbsGCtrl.text = (calories * cPct / 100 / 4).toStringAsFixed(0);
      _fatGCtrl.text = (calories * fPct / 100 / 9).toStringAsFixed(0);
    });
  }

  void _addAllergy() {
    final text = _allergyCtrl.text.trim();
    if (text.isNotEmpty && !_allergies.contains(text)) {
      setState(() {
        _allergies.add(text);
        _allergyCtrl.clear();
      });
    }
  }

  void _removeAllergy(String allergy) {
    setState(() => _allergies.remove(allergy));
  }

  UserProfile _buildProfile() {
    return UserProfile(
      calories: double.tryParse(_caloriesCtrl.text.trim()) ?? 2000,
      proteinG: double.tryParse(_proteinGCtrl.text.trim()) ?? 150,
      carbsG: double.tryParse(_carbsGCtrl.text.trim()) ?? 200,
      fatG: double.tryParse(_fatGCtrl.text.trim()) ?? 67,
      proteinPct: double.tryParse(_proteinPctCtrl.text.trim()) ?? 30,
      carbsPct: double.tryParse(_carbsPctCtrl.text.trim()) ?? 40,
      fatPct: double.tryParse(_fatPctCtrl.text.trim()) ?? 30,
      calorieDeficitMode: _calorieDeficitMode,
      demographicGroup: _demographicGroup,
      allergies: List.from(_allergies),
      micronutrientGoals: MicronutrientGoals(
        vitaminAUg: double.tryParse(_vitaminACtrl.text.trim()) ?? 0,
        vitaminCMg: double.tryParse(_vitaminCCtrl.text.trim()) ?? 0,
        ironMg: double.tryParse(_ironCtrl.text.trim()) ?? 0,
        calciumMg: double.tryParse(_calciumCtrl.text.trim()) ?? 0,
        fiberG: double.tryParse(_fiberCtrl.text.trim()) ?? 0,
        sodiumMg: double.tryParse(_sodiumCtrl.text.trim()) ?? 0,
      ),
      ingredientApiKey: _ingredientApiKeyCtrl.text.trim(),
      llmApiKey: _llmApiKeyCtrl.text.trim(),
    );
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    final profile = _buildProfile();
    await context.read<ProfileProvider>().saveProfile(profile);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Profile saved')),
      );
    }
  }

  void _cancel() {
    setState(() {
      _initialized = false;
    });
    _loadFromProvider();
    setState(() {
      _initialized = true;
    });
  }

  String? _requiredNumber(String? value) {
    if (value == null || value.trim().isEmpty) return 'Required';
    if (double.tryParse(value.trim()) == null) return 'Enter a valid number';
    return null;
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final maxWidth = constraints.maxWidth > 600 ? 560.0 : double.infinity;

        return SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Center(
            child: ConstrainedBox(
              constraints: BoxConstraints(maxWidth: maxWidth),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Profile & Settings',
                      style: Theme.of(context).textTheme.headlineMedium,
                    ),
                    const SizedBox(height: 24),

                    // Editable Nutrition Targets
                    const SectionHeader(title: 'Editable Nutrition Targets'),
                    Row(
                      children: [
                        Expanded(
                          child: TextFormField(
                            controller: _proteinPctCtrl,
                            decoration: const InputDecoration(
                              labelText: 'Protein',
                              suffixText: '%',
                            ),
                            keyboardType: TextInputType.number,
                            validator: _requiredNumber,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: TextFormField(
                            controller: _carbsPctCtrl,
                            decoration: const InputDecoration(
                              labelText: 'Carbs',
                              suffixText: '%',
                            ),
                            keyboardType: TextInputType.number,
                            validator: _requiredNumber,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: TextFormField(
                            controller: _fatPctCtrl,
                            decoration: const InputDecoration(
                              labelText: 'Fats',
                              suffixText: '%',
                            ),
                            keyboardType: TextInputType.number,
                            validator: _requiredNumber,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: _totalCaloriesCtrl,
                      decoration: const InputDecoration(
                        labelText: 'Total Calories',
                        suffixText: 'kcal',
                      ),
                      keyboardType: TextInputType.number,
                      validator: _requiredNumber,
                    ),
                    const SizedBox(height: 12),
                    FilledButton.tonal(
                      onPressed: _calculateFromRatios,
                      child: const Text('Calculate from Ratios'),
                    ),
                    const SizedBox(height: 16),

                    // Calorie Deficit Mode
                    SwitchListTile(
                      contentPadding: EdgeInsets.zero,
                      title: const Text('Calorie Deficit Mode'),
                      subtitle: const Text(
                        'Enable to automatically reduce calorie target',
                      ),
                      value: _calorieDeficitMode,
                      onChanged: (v) =>
                          setState(() => _calorieDeficitMode = v),
                    ),
                    const SizedBox(height: 12),

                    // Manual macro inputs
                    TextFormField(
                      controller: _caloriesCtrl,
                      decoration: const InputDecoration(
                        labelText: 'Calories',
                        suffixText: 'kcal',
                      ),
                      keyboardType: TextInputType.number,
                      validator: _requiredNumber,
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: _proteinGCtrl,
                      decoration: const InputDecoration(
                        labelText: 'Protein',
                        suffixText: 'g',
                      ),
                      keyboardType: TextInputType.number,
                      validator: _requiredNumber,
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: _carbsGCtrl,
                      decoration: const InputDecoration(
                        labelText: 'Carbs',
                        suffixText: 'g',
                      ),
                      keyboardType: TextInputType.number,
                      validator: _requiredNumber,
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: _fatGCtrl,
                      decoration: const InputDecoration(
                        labelText: 'Fats',
                        suffixText: 'g',
                      ),
                      keyboardType: TextInputType.number,
                      validator: _requiredNumber,
                    ),
                    const SizedBox(height: 24),

                    // User Demographics
                    const SectionHeader(title: 'User Demographics'),
                    DropdownButtonFormField<String>(
                      initialValue: _demographicGroup,
                      decoration: const InputDecoration(
                        labelText: 'Demographic Group',
                      ),
                      items: _demographicOptions
                          .map((v) => DropdownMenuItem(
                                value: v,
                                child: Text(_demographicLabels[v] ?? v),
                              ))
                          .toList(),
                      onChanged: (v) =>
                          setState(() => _demographicGroup = v ?? ''),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Used to calculate appropriate Upper Limits (UL) for micronutrients',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: Theme.of(context)
                                .colorScheme
                                .onSurfaceVariant,
                          ),
                    ),
                    const SizedBox(height: 24),

                    // Allergies & Dietary Restrictions
                    const SectionHeader(
                        title: 'Allergies & Dietary Restrictions'),
                    Row(
                      children: [
                        Expanded(
                          child: TextFormField(
                            controller: _allergyCtrl,
                            decoration: const InputDecoration(
                              hintText: 'Type allergy or restriction...',
                            ),
                            onFieldSubmitted: (_) => _addAllergy(),
                          ),
                        ),
                        const SizedBox(width: 8),
                        FilledButton(
                          onPressed: _addAllergy,
                          child: const Text('Add'),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    if (_allergies.isEmpty)
                      Text(
                        'No allergies added - meal plans will consider all ingredients',
                        style:
                            Theme.of(context).textTheme.bodySmall?.copyWith(
                                  color: Theme.of(context)
                                      .colorScheme
                                      .onSurfaceVariant,
                                ),
                      )
                    else
                      Wrap(
                        spacing: 8,
                        runSpacing: 4,
                        children: _allergies
                            .map((a) => Chip(
                                  label: Text(a),
                                  onDeleted: () => _removeAllergy(a),
                                ))
                            .toList(),
                      ),
                    const SizedBox(height: 24),

                    // Micronutrient Goals
                    const SectionHeader(title: 'Micronutrient Goals'),
                    Row(
                      children: [
                        Expanded(
                          child: TextFormField(
                            controller: _vitaminACtrl,
                            decoration: const InputDecoration(
                              labelText: 'Vitamin A',
                              suffixText: 'mcg',
                            ),
                            keyboardType: TextInputType.number,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: TextFormField(
                            controller: _vitaminCCtrl,
                            decoration: const InputDecoration(
                              labelText: 'Vitamin C',
                              suffixText: 'mg',
                            ),
                            keyboardType: TextInputType.number,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        Expanded(
                          child: TextFormField(
                            controller: _ironCtrl,
                            decoration: const InputDecoration(
                              labelText: 'Iron',
                              suffixText: 'mg',
                            ),
                            keyboardType: TextInputType.number,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: TextFormField(
                            controller: _calciumCtrl,
                            decoration: const InputDecoration(
                              labelText: 'Calcium',
                              suffixText: 'mg',
                            ),
                            keyboardType: TextInputType.number,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        Expanded(
                          child: TextFormField(
                            controller: _fiberCtrl,
                            decoration: const InputDecoration(
                              labelText: 'Fiber',
                              suffixText: 'g',
                            ),
                            keyboardType: TextInputType.number,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: TextFormField(
                            controller: _sodiumCtrl,
                            decoration: const InputDecoration(
                              labelText: 'Sodium',
                              suffixText: 'mg',
                            ),
                            keyboardType: TextInputType.number,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 24),

                    // API Configuration
                    const SectionHeader(title: 'API Configuration'),
                    TextFormField(
                      controller: _ingredientApiKeyCtrl,
                      decoration: const InputDecoration(
                        labelText: 'Ingredient API Key',
                      ),
                      obscureText: true,
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: _llmApiKeyCtrl,
                      decoration: const InputDecoration(
                        labelText: 'LLM API Key',
                      ),
                      obscureText: true,
                    ),
                    const SizedBox(height: 32),

                    // Action buttons
                    Row(
                      mainAxisAlignment: MainAxisAlignment.end,
                      children: [
                        OutlinedButton(
                          onPressed: _cancel,
                          child: const Text('Cancel'),
                        ),
                        const SizedBox(width: 12),
                        FilledButton(
                          onPressed: _save,
                          child: const Text('Save Profile'),
                        ),
                      ],
                    ),
                    const SizedBox(height: 24),
                  ],
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}
