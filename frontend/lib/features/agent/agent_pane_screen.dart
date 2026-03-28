import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../providers/meal_plan_provider.dart';
import '../../providers/recipe_provider.dart';
import '../../services/api_service.dart';
import '../../widgets/app_shell.dart';
import '../../widgets/section_header.dart';
import 'agent_api.dart';
import 'agent_models.dart';
import 'llm_config_provider.dart';

/// Primary surface for NL plan, ingredient match, and validated recipe generation.
class AgentPaneScreen extends StatefulWidget {
  const AgentPaneScreen({super.key});

  @override
  State<AgentPaneScreen> createState() => _AgentPaneScreenState();
}

class _AgentPaneScreenState extends State<AgentPaneScreen> {
  final _nlCtrl = TextEditingController();
  final _matchCtrl = TextEditingController();
  final _genCountCtrl = TextEditingController(text: '2');
  final _genContextCtrl = TextEditingController(text: '{}');

  bool _nlLoading = false;
  bool _matchLoading = false;
  bool _genLoading = false;
  IngredientMatchResult? _matchResult;
  RecipeGenerationResult? _genResult;
  String? _sectionError;

  @override
  void dispose() {
    _nlCtrl.dispose();
    _matchCtrl.dispose();
    _genCountCtrl.dispose();
    _genContextCtrl.dispose();
    super.dispose();
  }

  void _toast(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  Future<void> _runNlPlan() async {
    final gate = context.read<LlmConfigProvider>();
    if (!gate.llmReady) return;
    final prompt = _nlCtrl.text.trim();
    if (prompt.isEmpty) {
      _toast('Enter a prompt.');
      return;
    }
    final meal = context.read<MealPlanProvider>();
    setState(() {
      _nlLoading = true;
      _sectionError = null;
    });
    try {
      final plan = await AgentApi.planFromText({
        'prompt': prompt,
        'ingredient_source': meal.ingredientSource,
        'planning_mode': 'assisted',
      });
      if (!mounted) return;
      context.read<MealPlanProvider>().applyPlanResult(plan);
      _toast('Plan generated');
      context.findAncestorStateOfType<AppShellState>()?.navigateTo(5);
    } on ApiException catch (e) {
      if (!mounted) return;
      gate.revokeReady(e.message);
      setState(() => _sectionError = e.message);
    } catch (e) {
      if (!mounted) return;
      gate.revokeReady(e.toString());
      setState(() => _sectionError = e.toString());
    } finally {
      if (mounted) setState(() => _nlLoading = false);
    }
  }

  Future<void> _runMatch() async {
    final gate = context.read<LlmConfigProvider>();
    if (!gate.llmReady) return;
    final raw = _matchCtrl.text.trim();
    if (raw.isEmpty) {
      _toast('Enter one ingredient per line.');
      return;
    }
    final queries = raw
        .split(RegExp(r'\r?\n'))
        .map((s) => s.trim())
        .where((s) => s.isNotEmpty)
        .toList();
    if (queries.isEmpty) {
      _toast('No queries to match.');
      return;
    }
    setState(() {
      _matchLoading = true;
      _matchResult = null;
      _sectionError = null;
    });
    try {
      final result = await AgentApi.matchIngredients(queries);
      if (!mounted) return;
      setState(() => _matchResult = result);
    } on ApiException catch (e) {
      if (!mounted) return;
      gate.revokeReady(e.message);
      setState(() => _sectionError = e.message);
    } catch (e) {
      if (!mounted) return;
      gate.revokeReady(e.toString());
      setState(() => _sectionError = e.toString());
    } finally {
      if (mounted) setState(() => _matchLoading = false);
    }
  }

  Future<void> _runGenerate() async {
    final gate = context.read<LlmConfigProvider>();
    if (!gate.llmReady) return;
    final count = int.tryParse(_genCountCtrl.text.trim());
    if (count == null || count < 1 || count > 20) {
      _toast('Count must be 1–20.');
      return;
    }
    Map<String, dynamic> ctx;
    try {
      final decoded = jsonDecode(_genContextCtrl.text.trim());
      if (decoded is! Map) {
        _toast('Context must be a JSON object.');
        return;
      }
      ctx = Map<String, dynamic>.from(decoded);
    } catch (_) {
      _toast('Invalid JSON for context.');
      return;
    }
    setState(() {
      _genLoading = true;
      _genResult = null;
      _sectionError = null;
    });
    try {
      final result = await AgentApi.generateValidatedRecipes(
        count: count,
        context: ctx,
      );
      if (!mounted) return;
      setState(() => _genResult = result);
      await context.read<RecipeProvider>().syncSummariesFromApi();
      _toast(
        'Accepted ${result.acceptedCount} recipe(s). Refresh Library for details.',
      );
    } on ApiException catch (e) {
      if (!mounted) return;
      gate.revokeReady(e.message);
      setState(() => _sectionError = e.message);
    } catch (e) {
      if (!mounted) return;
      gate.revokeReady(e.toString());
      setState(() => _sectionError = e.toString());
    } finally {
      if (mounted) setState(() => _genLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final gate = context.watch<LlmConfigProvider>();
    if (!gate.llmReady) {
      return const Center(child: Text('LLM gate closed.'));
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 640),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Agent',
                style: Theme.of(context).textTheme.headlineMedium,
              ),
              const SizedBox(height: 8),
              Text(
                'Requires LLM configured on the server. Client validation only '
                'confirms you entered credentials here.',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
              ),
              if (_sectionError != null) ...[
                const SizedBox(height: 12),
                Text(
                  _sectionError!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ],
              const SizedBox(height: 24),
              const SectionHeader(title: 'Plan from text'),
              TextField(
                controller: _nlCtrl,
                decoration: const InputDecoration(
                  hintText: 'e.g. High protein vegetarian week, 3 meals…',
                  border: OutlineInputBorder(),
                ),
                minLines: 2,
                maxLines: 5,
              ),
              const SizedBox(height: 12),
              FilledButton.icon(
                onPressed: _nlLoading ? null : _runNlPlan,
                icon: _nlLoading
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.auto_awesome),
                label: Text(_nlLoading ? 'Generating…' : 'Generate plan'),
              ),
              const SizedBox(height: 32),
              const SectionHeader(title: 'Match ingredient names'),
              TextField(
                controller: _matchCtrl,
                decoration: const InputDecoration(
                  hintText: 'One ingredient per line',
                  border: OutlineInputBorder(),
                ),
                minLines: 4,
                maxLines: 10,
              ),
              const SizedBox(height: 12),
              FilledButton.tonalIcon(
                onPressed: _matchLoading ? null : _runMatch,
                icon: _matchLoading
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.join_inner),
                label: Text(_matchLoading ? 'Matching…' : 'AI match'),
              ),
              if (_matchResult != null) ...[
                const SizedBox(height: 12),
                ..._matchResult!.accepted.map(
                  (a) => ListTile(
                    dense: true,
                    leading: const Icon(Icons.check_circle_outline),
                    title: Text(a.normalizedName),
                    subtitle: Text(
                      '${a.originalQuery} · ${(a.confidence * 100).toStringAsFixed(0)}%',
                    ),
                  ),
                ),
                ..._matchResult!.rejected.map(
                  (r) => ListTile(
                    dense: true,
                    leading: Icon(Icons.error_outline,
                        color: Theme.of(context).colorScheme.error),
                    title: Text(r.originalQuery),
                    subtitle: Text('${r.code}: ${r.message}'),
                  ),
                ),
              ],
              const SizedBox(height: 32),
              const SectionHeader(title: 'Generate validated recipes'),
              TextField(
                controller: _genCountCtrl,
                decoration: const InputDecoration(
                  labelText: 'Count (1–20)',
                  border: OutlineInputBorder(),
                ),
                keyboardType: TextInputType.number,
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _genContextCtrl,
                decoration: const InputDecoration(
                  labelText: 'Context JSON',
                  alignLabelWithHint: true,
                  border: OutlineInputBorder(),
                  hintText: '{"theme":"Mediterranean"}',
                ),
                minLines: 2,
                maxLines: 6,
              ),
              const SizedBox(height: 12),
              FilledButton.tonalIcon(
                onPressed: _genLoading ? null : _runGenerate,
                icon: _genLoading
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.restaurant_menu),
                label: Text(_genLoading ? 'Generating…' : 'Generate & persist'),
              ),
              if (_genResult != null) ...[
                const SizedBox(height: 12),
                Text(
                  'Accepted: ${_genResult!.acceptedCount}, rejected: '
                  '${_genResult!.rejectedCount}',
                  style: Theme.of(context).textTheme.titleSmall,
                ),
                SelectableText(_genResult!.recipeIds.join(', ')),
                ..._genResult!.failures.map(
                  (f) => Text('${f.code}: ${f.message}',
                      style: TextStyle(
                          color: Theme.of(context).colorScheme.error)),
                ),
              ],
              const SizedBox(height: 48),
            ],
          ),
        ),
      ),
    );
  }
}
