import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../providers/meal_plan_provider.dart';
import '../../providers/recipe_provider.dart';
import '../../services/api_service.dart';
import '../../theme/tokens.dart';
import '../../widgets/advisory_card.dart';
import '../../widgets/app_shell.dart';
import '../../widgets/confidence_chip.dart';
import '../../widgets/empty_state.dart';
import '../../widgets/section_header.dart';
import 'agent_api.dart';
import 'agent_models.dart';
import 'llm_config_provider.dart';

ConfidenceLevel confidenceFromScore(double confidence) {
  if (confidence >= 0.8) return ConfidenceLevel.hi;
  if (confidence >= 0.5) return ConfidenceLevel.mid;
  return ConfidenceLevel.none;
}

/// API/section error surface for the agent pane (shared with widget tests).
class AgentSectionErrorBanner extends StatelessWidget {
  const AgentSectionErrorBanner({super.key, required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return AdvisoryCard(
      variant: AdvisoryVariant.warn,
      title: 'Request failed',
      description: message,
    );
  }
}

/// Match result rows for the agent pane (shared with widget tests).
class AgentMatchResultsSection extends StatelessWidget {
  const AgentMatchResultsSection({super.key, required this.result});

  final IngredientMatchResult result;

  @override
  Widget build(BuildContext context) {
    final tokens =
        Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        ...result.accepted.map(
          (a) => Padding(
            padding: const EdgeInsets.only(bottom: MacrovaSpacing.sm),
            child: _AgentMatchRow(
              title: a.normalizedName,
              subtitle: a.originalQuery,
              trailing: ConfidenceChip(
                level: confidenceFromScore(a.confidence),
                label: '${(a.confidence * 100).toStringAsFixed(0)}% match',
              ),
              tokens: tokens,
            ),
          ),
        ),
        ...result.rejected.map(
          (r) => Padding(
            padding: const EdgeInsets.only(bottom: MacrovaSpacing.sm),
            child: _AgentMatchRow(
              title: r.originalQuery,
              subtitle: '${r.code}: ${r.message}',
              subtitleColor: tokens.accentDeep,
              leading: Icon(
                Icons.error_outline,
                size: 16,
                color: tokens.accentDeep,
              ),
              accent: true,
              tokens: tokens,
            ),
          ),
        ),
      ],
    );
  }
}

/// Generation result summary for the agent pane (shared with widget tests).
class AgentGenerationResultsSection extends StatelessWidget {
  const AgentGenerationResultsSection({super.key, required this.result});

  final RecipeGenerationResult result;

  @override
  Widget build(BuildContext context) {
    final tokens =
        Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        AdvisoryCard(
          variant: AdvisoryVariant.info,
          title:
              'Accepted ${result.acceptedCount}, rejected ${result.rejectedCount}',
          description: result.recipeIds.isEmpty
              ? 'No recipe IDs returned.'
              : 'Recipe IDs (select to copy):',
        ),
        if (result.recipeIds.isNotEmpty) ...[
          const SizedBox(height: MacrovaSpacing.sm),
          ...result.recipeIds.map(
            (id) => Padding(
              padding: const EdgeInsets.only(bottom: MacrovaSpacing.sm),
              child: _AgentGenRow(
                label: id,
                done: true,
                tokens: tokens,
              ),
            ),
          ),
          SelectableText(
            result.recipeIds.join(', '),
            style: MacrovaTypography.caption(tokens.inkSecondary),
          ),
        ],
        if (result.failures.isNotEmpty) ...[
          const SizedBox(height: MacrovaSpacing.md),
          ...result.failures.map(
            (f) => Padding(
              padding: const EdgeInsets.only(bottom: MacrovaSpacing.sm),
              child: AdvisoryCard(
                variant: AdvisoryVariant.warn,
                title: f.code,
                description: f.message,
              ),
            ),
          ),
        ],
      ],
    );
  }
}

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

  Widget _loadingIcon(BuildContext context) {
    final tokens =
        Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;
    return SizedBox(
      width: 18,
      height: 18,
      child: CircularProgressIndicator(
        strokeWidth: 2.5,
        color: tokens.accent,
        backgroundColor: tokens.lineSoft,
      ),
    );
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
      context.findAncestorStateOfType<AppShellState>()?.navigateTo(6);
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
    final tokens =
        Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;

    if (!gate.llmReady) {
      return const _AgentGateClosedFallback();
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(MacrovaSpacing.xlAlt),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 640),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Agent',
                style: MacrovaTypography.headline(tokens.inkPrimary),
              ),
              const SizedBox(height: MacrovaSpacing.sm),
              Text(
                'Requires LLM configured on the server. Client validation only '
                'confirms you entered credentials here.',
                style: MacrovaTypography.body(tokens.inkTertiary),
              ),
              if (_sectionError != null) ...[
                const SizedBox(height: MacrovaSpacing.md),
                AgentSectionErrorBanner(message: _sectionError!),
              ],
              const SizedBox(height: MacrovaSpacing.xlAlt),
              _AgentPromptCard(
                controller: _nlCtrl,
                loading: _nlLoading,
                loadingIcon: _loadingIcon(context),
                onGenerate: _runNlPlan,
              ),
              const SizedBox(height: MacrovaSpacing.xxl),
              _AgentSectionCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const SectionHeader(
                      title: 'Match ingredient names',
                      subtitle: 'One query per line · real confidence from match API',
                    ),
                    TextField(
                      controller: _matchCtrl,
                      decoration: const InputDecoration(
                        hintText: 'One ingredient per line',
                      ),
                      minLines: 4,
                      maxLines: 10,
                    ),
                    const SizedBox(height: MacrovaSpacing.md),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: FilledButton.tonalIcon(
                        onPressed: _matchLoading ? null : _runMatch,
                        icon: _matchLoading
                            ? _loadingIcon(context)
                            : const Icon(Icons.join_inner),
                        label: Text(
                          _matchLoading ? 'Matching…' : 'AI match',
                        ),
                      ),
                    ),
                    if (_matchLoading && _matchResult == null) ...[
                      const SizedBox(height: MacrovaSpacing.md),
                      const EmptyState.loading(label: 'Matching ingredients…'),
                    ],
                    if (_matchResult != null) ...[
                      const SizedBox(height: MacrovaSpacing.md),
                      AgentMatchResultsSection(result: _matchResult!),
                    ],
                  ],
                ),
              ),
              const SizedBox(height: MacrovaSpacing.xxl),
              _AgentSectionCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const SectionHeader(
                      title: 'Generate validated recipes',
                      subtitle:
                          'Generate → validate → persist only if nutrition checks pass',
                    ),
                    TextField(
                      controller: _genCountCtrl,
                      decoration: const InputDecoration(
                        labelText: 'Count (1–20)',
                      ),
                      keyboardType: TextInputType.number,
                    ),
                    const SizedBox(height: MacrovaSpacing.md),
                    TextField(
                      controller: _genContextCtrl,
                      decoration: const InputDecoration(
                        labelText: 'Context JSON',
                        alignLabelWithHint: true,
                        hintText: '{"theme":"Mediterranean"}',
                      ),
                      minLines: 2,
                      maxLines: 6,
                    ),
                    const SizedBox(height: MacrovaSpacing.md),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: FilledButton.tonalIcon(
                        onPressed: _genLoading ? null : _runGenerate,
                        icon: _genLoading
                            ? _loadingIcon(context)
                            : const Icon(Icons.restaurant_menu),
                        label: Text(
                          _genLoading ? 'Generating…' : 'Generate & persist',
                        ),
                      ),
                    ),
                    if (_genLoading && _genResult == null) ...[
                      const SizedBox(height: MacrovaSpacing.md),
                      _AgentGenRow(
                        label: 'Generating validated recipes…',
                        running: true,
                        tokens: tokens,
                      ),
                    ],
                    if (_genResult != null) ...[
                      const SizedBox(height: MacrovaSpacing.md),
                      AgentGenerationResultsSection(result: _genResult!),
                    ],
                  ],
                ),
              ),
              const SizedBox(height: MacrovaSpacing.xxl),
            ],
          ),
        ),
      ),
    );
  }
}

/// Tokenized fallback when the pane is shown with the LLM gate closed.
class _AgentGateClosedFallback extends StatelessWidget {
  const _AgentGateClosedFallback();

  @override
  Widget build(BuildContext context) {
    final tokens =
        Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;

    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(
          maxWidth: MacrovaSpacing.mobileMaxWidth,
        ),
        child: Padding(
          padding: const EdgeInsets.all(MacrovaSpacing.xxl),
          child: Container(
            width: double.infinity,
            padding: const EdgeInsets.all(MacrovaSpacing.xlAlt),
            decoration: BoxDecoration(
              color: tokens.surfaceTint,
              borderRadius: MacrovaRadius.borderLg,
              border: Border.all(color: tokens.lineDefault),
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 56,
                  height: 56,
                  decoration: BoxDecoration(
                    color: tokens.accentSoft,
                    shape: BoxShape.circle,
                    border: Border.all(color: tokens.accentTint),
                  ),
                  alignment: Alignment.center,
                  child: Icon(
                    Icons.lock_outline,
                    size: 28,
                    color: tokens.accent,
                  ),
                ),
                const SizedBox(height: MacrovaSpacing.xlAlt),
                Text(
                  'LLM gate closed.',
                  style: MacrovaTypography.titleSm(tokens.inkPrimary),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: MacrovaSpacing.sm),
                Text(
                  'Validate LLM credentials on Profile to unlock Agent actions.',
                  style: MacrovaTypography.bodyMedium(tokens.inkTertiary),
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Accent-soft prompt surface for NL plan-from-text input.
class _AgentPromptCard extends StatelessWidget {
  const _AgentPromptCard({
    required this.controller,
    required this.loading,
    required this.loadingIcon,
    required this.onGenerate,
  });

  final TextEditingController controller;
  final bool loading;
  final Widget loadingIcon;
  final VoidCallback onGenerate;

  @override
  Widget build(BuildContext context) {
    final tokens =
        Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;
    final isDark = tokens.isDark;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(MacrovaSpacing.lgAlt),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: isDark
              ? [tokens.accentSoft, tokens.accentTint]
              : const [
                  MacrovaColors.accentSoft,
                  Color(0xFFFAE8E2),
                ],
        ),
        borderRadius: MacrovaRadius.borderLg,
        border: Border.all(color: tokens.accentTint),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            MacrovaTypography.labelCapsText('You said'),
            style: MacrovaTypography.labelCaps(tokens.accentDeep),
          ),
          const SizedBox(height: MacrovaSpacing.sm),
          const SectionHeader(
            title: 'Plan from text',
            subtitle: 'Natural language → assisted plan-from-text',
          ),
          TextField(
            controller: controller,
            style: MacrovaTypography.subtitle(tokens.inkPrimary).copyWith(
              fontWeight: FontWeight.w500,
            ),
            decoration: InputDecoration(
              hintText: 'e.g. High protein vegetarian week, 3 meals…',
              filled: true,
              fillColor: isDark
                  ? MacrovaColorsDark.surfaceCard
                  : MacrovaColors.surfaceCard,
            ),
            minLines: 2,
            maxLines: 5,
          ),
          const SizedBox(height: MacrovaSpacing.md),
          Align(
            alignment: Alignment.centerLeft,
            child: FilledButton.icon(
              onPressed: loading ? null : onGenerate,
              icon: loading ? loadingIcon : const Icon(Icons.auto_awesome),
              label: Text(loading ? 'Generating…' : 'Generate plan'),
            ),
          ),
        ],
      ),
    );
  }
}

/// Hairline card shell for Match / Generate sections.
class _AgentSectionCard extends StatelessWidget {
  const _AgentSectionCard({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    final tokens =
        Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(MacrovaSpacing.lg),
      decoration: BoxDecoration(
        color: tokens.isDark
            ? MacrovaColorsDark.surfaceCard
            : MacrovaColors.surfaceCard,
        borderRadius: MacrovaRadius.borderLg,
        border: Border.all(color: tokens.lineDefault),
        boxShadow: MacrovaElevation.shadow1,
      ),
      child: child,
    );
  }
}

/// Match / reject row styled like prototype parse/match cards.
class _AgentMatchRow extends StatelessWidget {
  const _AgentMatchRow({
    required this.title,
    required this.subtitle,
    required this.tokens,
    this.trailing,
    this.leading,
    this.subtitleColor,
    this.accent = false,
  });

  final String title;
  final String subtitle;
  final MacrovaTokens tokens;
  final Widget? trailing;
  final Widget? leading;
  final Color? subtitleColor;
  final bool accent;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(MacrovaSpacing.md),
      decoration: BoxDecoration(
        color: accent
            ? tokens.accentSoft
            : (tokens.isDark
                ? MacrovaColorsDark.surfaceCard
                : MacrovaColors.surfaceCard),
        borderRadius: MacrovaRadius.borderSm,
        border: Border.all(
          color: accent ? tokens.accentTint : tokens.lineDefault,
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (leading != null) ...[
            leading!,
            const SizedBox(width: MacrovaSpacing.sm),
          ],
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: MacrovaTypography.label(tokens.inkPrimary),
                ),
                const SizedBox(height: MacrovaSpacing.xs),
                Text(
                  subtitle,
                  style: MacrovaTypography.caption(
                    subtitleColor ?? tokens.inkTertiary,
                  ),
                ),
              ],
            ),
          ),
          if (trailing != null) ...[
            const SizedBox(width: MacrovaSpacing.sm),
            trailing!,
          ],
        ],
      ),
    );
  }
}

/// Gen-row presentation tied to real loading / done state (no fake phases).
class _AgentGenRow extends StatelessWidget {
  const _AgentGenRow({
    required this.label,
    required this.tokens,
    this.running = false,
    this.done = false,
  });

  final String label;
  final MacrovaTokens tokens;
  final bool running;
  final bool done;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(MacrovaSpacing.md),
      decoration: BoxDecoration(
        color: tokens.isDark
            ? MacrovaColorsDark.surfaceCard
            : MacrovaColors.surfaceCard,
        borderRadius: MacrovaRadius.borderSm,
        border: Border.all(color: tokens.lineDefault),
      ),
      child: Row(
        children: [
          if (running)
            SizedBox(
              width: 22,
              height: 22,
              child: CircularProgressIndicator(
                strokeWidth: 2.5,
                color: tokens.accent,
                backgroundColor: tokens.lineSoft,
              ),
            )
          else
            Container(
              width: 26,
              height: 26,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: done
                    ? tokens.semanticSuccessText
                    : tokens.surfaceSoft,
              ),
              alignment: Alignment.center,
              child: done
                  ? const Icon(
                      Icons.check,
                      size: 14,
                      color: MacrovaColors.onDarkFill,
                    )
                  : null,
            ),
          const SizedBox(width: MacrovaSpacing.md),
          Expanded(
            child: Text(
              label,
              style: MacrovaTypography.label(tokens.inkPrimary),
            ),
          ),
        ],
      ),
    );
  }
}
