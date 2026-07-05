import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:uuid/uuid.dart';

import '../models/ingredient.dart';
import '../features/agent/agent_api.dart';
import '../features/agent/llm_config_provider.dart';
import '../models/ingredient_search.dart';
import '../models/micronutrient_metadata.dart';
import '../providers/ingredient_provider.dart';
import '../providers/profile_provider.dart';
import '../services/api_service.dart';
import '../theme/tokens.dart';
import '../widgets/advisory_card.dart';
import '../widgets/confidence_chip.dart';
import '../widgets/empty_state.dart';
import '../widgets/ingredient_card.dart';
import '../widgets/macro_display.dart';
import '../widgets/macrova_chip.dart';
import '../widgets/micronutrient_bar.dart';
import '../widgets/section_header.dart';

const _uuid = Uuid();

/// Maps a 0..1 match confidence into a [ConfidenceLevel] band.
ConfidenceLevel _confidenceLevel(double confidence) {
  if (confidence >= 0.75) return ConfidenceLevel.hi;
  if (confidence >= 0.5) return ConfidenceLevel.mid;
  return ConfidenceLevel.none;
}

/// Keys present on [Ingredient.micronutrientsPer100g], ordered like profile / plan UI.
List<MapEntry<String, double>> _micronutrientEntriesInDisplayOrder(
  Map<String, double> micros,
) {
  final rank = {
    for (var i = 0; i < kMicronutrientsInDisplayOrder.length; i++)
      kMicronutrientsInDisplayOrder[i].key: i,
  };
  return micros.entries.toList()
    ..sort((a, b) {
      final ra = rank[a.key] ?? 1000;
      final rb = rank[b.key] ?? 1000;
      if (ra != rb) return ra.compareTo(rb);
      return a.key.compareTo(b.key);
    });
}

class IngredientHubScreen extends StatefulWidget {
  const IngredientHubScreen({super.key});

  @override
  State<IngredientHubScreen> createState() => _IngredientHubScreenState();
}

class _IngredientHubScreenState extends State<IngredientHubScreen> {
  final _searchCtrl = TextEditingController();
  IngredientSource? _sourceFilter;
  String? _selectedId;
  bool _remoteUsdaMode = false;
  /// When true, remote search uses `data_types=sr_legacy_only` on the API.
  bool _remoteSrLegacyOnly = false;
  Timer? _remoteDebounce;
  List<IngredientSearchResultItem> _remoteResults = [];
  bool _remoteLoading = false;
  String? _remoteError;
  String? _resolvingFdcId;

  @override
  void dispose() {
    _remoteDebounce?.cancel();
    _searchCtrl.dispose();
    super.dispose();
  }

  void _onSearchTextChanged(String _) {
    if (_remoteUsdaMode) {
      _remoteDebounce?.cancel();
      _remoteDebounce = Timer(const Duration(milliseconds: 420), () {
        final q = _searchCtrl.text.trim();
        if (!mounted) return;
        _runRemoteSearch(q);
      });
    } else {
      setState(() {});
    }
  }

  Future<void> _runRemoteSearch(String query) async {
    if (query.isEmpty) {
      setState(() {
        _remoteResults = [];
        _remoteLoading = false;
        _remoteError = null;
      });
      return;
    }
    setState(() {
      _remoteLoading = true;
      _remoteError = null;
    });
    try {
      final res = await ApiService.searchIngredients(
        q: query,
        dataTypes: _remoteSrLegacyOnly ? 'sr_legacy_only' : 'all',
      );
      if (!mounted) return;
      setState(() {
        _remoteResults = res.results;
        _remoteLoading = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _remoteResults = [];
        _remoteLoading = false;
        _remoteError = '${e.code}: ${e.message}';
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _remoteResults = [];
        _remoteLoading = false;
        _remoteError = e.toString();
      });
    }
  }

  void _enterRemoteMode() {
    setState(() {
      _remoteUsdaMode = true;
      _sourceFilter = null;
      _selectedId = null;
    });
    final q = _searchCtrl.text.trim();
    if (q.isNotEmpty) {
      _remoteDebounce?.cancel();
      _runRemoteSearch(q);
    } else {
      setState(() {
        _remoteResults = [];
        _remoteError = null;
      });
    }
  }

  void _leaveRemoteMode() {
    _remoteDebounce?.cancel();
    setState(() {
      _remoteUsdaMode = false;
      _remoteSrLegacyOnly = false;
      _remoteResults = [];
      _remoteLoading = false;
      _remoteError = null;
      _resolvingFdcId = null;
    });
  }

  void _setRemoteSrLegacyOnly(bool value) {
    setState(() => _remoteSrLegacyOnly = value);
    if (!_remoteUsdaMode) return;
    final q = _searchCtrl.text.trim();
    if (q.isEmpty) return;
    _remoteDebounce?.cancel();
    _runRemoteSearch(q);
  }

  Future<void> _resolveAndAdd(IngredientSearchResultItem item) async {
    final fdc = int.tryParse(item.fdcId);
    if (fdc == null) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Invalid FDC id')),
        );
      }
      return;
    }
    final ingredients = context.read<IngredientProvider>();
    setState(() => _resolvingFdcId = item.fdcId);
    try {
      final payload = await ApiService.resolveIngredientJson(fdcId: fdc);
      final ing = Ingredient.fromResolveResponse(payload);
      await ingredients.addIngredient(ing);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Added "${ing.name}" to saved ingredients')),
      );
    } on ApiException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.message)),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.toString())),
      );
    } finally {
      if (mounted) {
        setState(() => _resolvingFdcId = null);
      }
    }
  }

  Future<void> _showAiMatchDialog() async {
    final gate = context.read<LlmConfigProvider>();
    if (!gate.llmReady) return;
    final ctrl = TextEditingController();
    await showDialog<void>(
      context: context,
      builder: (ctx) {
        var busy = false;
        return StatefulBuilder(
          builder: (ctx, setDialogState) {
            return AlertDialog(
              title: const Text('AI ingredient match'),
              content: SizedBox(
                width: 420,
                height: 300,
                child: TextField(
                  controller: ctrl,
                  decoration: const InputDecoration(
                    hintText: 'One ingredient name per line',
                    border: OutlineInputBorder(),
                  ),
                  maxLines: 12,
                  enabled: !busy,
                ),
              ),
              actions: [
                TextButton(
                  onPressed: busy ? null : () => Navigator.of(ctx).pop(),
                  child: const Text('Cancel'),
                ),
                FilledButton(
                  onPressed: busy
                      ? null
                      : () async {
                          final hostContext = context;
                          final lines = ctrl.text
                              .split(RegExp(r'\r?\n'))
                              .map((s) => s.trim())
                              .where((s) => s.isNotEmpty)
                              .toList();
                          if (lines.isEmpty) return;
                          setDialogState(() => busy = true);
                          try {
                            final result =
                                await AgentApi.matchIngredients(lines);
                            if (!hostContext.mounted) return;
                            Navigator.of(ctx).pop();
                            if (!hostContext.mounted) return;
                            await showDialog<void>(
                              context: hostContext,
                              builder: (ctx2) => AlertDialog(
                                title: const Text('Match results'),
                                content: SizedBox(
                                  width: 420,
                                  height: 360,
                                  child: SingleChildScrollView(
                                    child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        const Text('Accepted'),
                                        ...result.accepted.map(
                                          (a) => ListTile(
                                            dense: true,
                                            title: Text(a.normalizedName),
                                            subtitle: Text(a.originalQuery),
                                            trailing: ConfidenceChip(
                                              level: _confidenceLevel(
                                                a.confidence,
                                              ),
                                              label:
                                                  '${(a.confidence * 100).toStringAsFixed(0)}%',
                                            ),
                                          ),
                                        ),
                                        const SizedBox(height: 12),
                                        const Text('Rejected'),
                                        ...result.rejected.map(
                                          (r) => ListTile(
                                            dense: true,
                                            title: Text(r.originalQuery),
                                            subtitle: Text(
                                              '${r.code}: ${r.message}',
                                            ),
                                            trailing: const ConfidenceChip(
                                              level: ConfidenceLevel.none,
                                            ),
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                ),
                                actions: [
                                  TextButton(
                                    onPressed: () =>
                                        Navigator.of(ctx2).pop(),
                                    child: const Text('Close'),
                                  ),
                                ],
                              ),
                            );
                          } on ApiException catch (e) {
                            if (!hostContext.mounted) return;
                            gate.revokeReady(e.message);
                            Navigator.of(ctx).pop();
                            if (!hostContext.mounted) return;
                            ScaffoldMessenger.of(hostContext).showSnackBar(
                              SnackBar(content: Text(e.message)),
                            );
                          } catch (e) {
                            if (!hostContext.mounted) return;
                            gate.revokeReady(e.toString());
                            Navigator.of(ctx).pop();
                            if (!hostContext.mounted) return;
                            ScaffoldMessenger.of(hostContext).showSnackBar(
                              SnackBar(content: Text(e.toString())),
                            );
                          }
                        },
                  child: Text(busy ? 'Running…' : 'Run'),
                ),
              ],
            );
          },
        );
      },
    );
    ctrl.dispose();
  }

  void _showCreateDialog() {
    showDialog<void>(
      context: context,
      builder: (ctx) => _CreateIngredientDialog(
        onSave: (ingredient) {
          context.read<IngredientProvider>().addIngredient(ingredient);
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<IngredientProvider>();
    final results = _remoteUsdaMode
        ? const <Ingredient>[]
        : provider.search(
            _searchCtrl.text,
            sourceFilter: _sourceFilter,
          );
    final selected =
        _selectedId != null ? provider.getById(_selectedId!) : null;

    final tokens = Theme.of(context).extension<MacrovaTokens>() ??
        MacrovaTokens.light;

    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth > 800;

        final listPanel = Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.all(MacrovaSpacing.lg),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _buildSearchField(tokens),
                  const SizedBox(height: MacrovaSpacing.md),
                  _buildFilterTabs(),
                  if (_remoteUsdaMode) ...[
                    const SizedBox(height: MacrovaSpacing.sm),
                    MacrovaChip(
                      label: 'SR Legacy only',
                      selected: _remoteSrLegacyOnly,
                      leadingIcon: _remoteSrLegacyOnly
                          ? Icons.check_circle
                          : Icons.filter_list_outlined,
                      onTap: () =>
                          _setRemoteSrLegacyOnly(!_remoteSrLegacyOnly),
                    ),
                    Padding(
                      padding: const EdgeInsets.only(top: MacrovaSpacing.xs),
                      child: Text(
                        _remoteSrLegacyOnly
                            ? 'USDA search is limited to SR Legacy (typical whole foods).'
                            : 'All FDC types: SR Legacy, Foundation, Survey, Branded.',
                        style: MacrovaTypography.caption(tokens.inkTertiary),
                      ),
                    ),
                  ],
                  if (_remoteUsdaMode && _remoteLoading)
                    Padding(
                      padding: const EdgeInsets.only(top: MacrovaSpacing.md),
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(MacrovaRadius.sm),
                        child: LinearProgressIndicator(
                          minHeight: 2,
                          color: tokens.accent,
                          backgroundColor: tokens.lineSoft,
                        ),
                      ),
                    ),
                  if (_remoteUsdaMode &&
                      _remoteError != null &&
                      !_remoteLoading)
                    Padding(
                      padding: const EdgeInsets.only(top: MacrovaSpacing.md),
                      child: AdvisoryCard(
                        variant: AdvisoryVariant.warn,
                        title: 'USDA search failed',
                        description: _remoteError!,
                      ),
                    ),
                ],
              ),
            ),
            Divider(height: 1, color: tokens.lineDefault),
            Expanded(
              child: _remoteUsdaMode
                  ? _buildRemoteResultsList(context)
                  : results.isEmpty
                      ? Center(
                          child: Padding(
                            padding: const EdgeInsets.all(MacrovaSpacing.xxl),
                            child: Text(
                              'No ingredients found',
                              textAlign: TextAlign.center,
                              style: MacrovaTypography.bodyMedium(
                                tokens.inkTertiary,
                              ),
                            ),
                          ),
                        )
                      : ListView.separated(
                          padding: const EdgeInsets.all(MacrovaSpacing.lg),
                          itemCount: results.length,
                          separatorBuilder: (_, __) =>
                              const SizedBox(height: MacrovaSpacing.sm),
                          itemBuilder: (_, i) {
                            final ing = results[i];
                            return IngredientCard(
                              ingredient: ing,
                              selected: ing.id == _selectedId,
                              onTap: () =>
                                  setState(() => _selectedId = ing.id),
                            );
                          },
                        ),
            ),
            Padding(
              padding: const EdgeInsets.all(MacrovaSpacing.lg),
              child: SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: _showCreateDialog,
                  icon: const Icon(Icons.add),
                  label: const Text('Create Custom Ingredient'),
                ),
              ),
            ),
            if (context.watch<LlmConfigProvider>().llmReady)
              Padding(
                padding: const EdgeInsets.fromLTRB(
                  MacrovaSpacing.lg,
                  0,
                  MacrovaSpacing.lg,
                  MacrovaSpacing.lg,
                ),
                child: SizedBox(
                  width: double.infinity,
                  child: FilledButton.tonalIcon(
                    onPressed: _showAiMatchDialog,
                    icon: const Icon(Icons.join_inner),
                    label: const Text('AI match ingredient names'),
                  ),
                ),
              ),
          ],
        );

        final detailPanel = selected != null
            ? _buildDetailPanel(context, selected)
            : Center(
                child: Padding(
                  padding: const EdgeInsets.all(MacrovaSpacing.xxl),
                  child: Text(
                    'Select an ingredient to view details',
                    textAlign: TextAlign.center,
                    style: MacrovaTypography.bodyMedium(tokens.inkTertiary),
                  ),
                ),
              );

        if (wide) {
          return Row(
            children: [
              Expanded(flex: 2, child: listPanel),
              VerticalDivider(width: 1, color: tokens.lineDefault),
              Expanded(flex: 3, child: detailPanel),
            ],
          );
        } else {
          return selected != null
              ? Column(
                  children: [
                    AppBar(
                      leading: IconButton(
                        icon: const Icon(Icons.arrow_back),
                        onPressed: () =>
                            setState(() => _selectedId = null),
                      ),
                      title: Text(selected.name),
                    ),
                    Expanded(child: detailPanel),
                  ],
                )
              : listPanel;
        }
      },
    );
  }

  Widget _buildSearchField(MacrovaTokens tokens) {
    return Container(
      decoration: BoxDecoration(
        color: tokens.surfaceSoft,
        borderRadius: MacrovaRadius.borderPill,
        border: Border.all(color: tokens.lineDefault),
      ),
      child: TextField(
        controller: _searchCtrl,
        style: MacrovaTypography.body(tokens.inkPrimary),
        decoration: InputDecoration(
          isDense: true,
          filled: false,
          hintText: _remoteUsdaMode
              ? 'Search USDA FoodData Central…'
              : 'Search for ingredients...',
          hintStyle: MacrovaTypography.body(tokens.inkTertiary),
          prefixIcon: Icon(Icons.search, color: tokens.inkTertiary, size: 20),
          border: InputBorder.none,
          enabledBorder: InputBorder.none,
          focusedBorder: InputBorder.none,
          contentPadding: const EdgeInsets.symmetric(
            horizontal: MacrovaSpacing.md,
            vertical: MacrovaSpacing.md,
          ),
        ),
        onChanged: _onSearchTextChanged,
      ),
    );
  }

  Widget _buildRemoteResultsList(BuildContext context) {
    final tokens = Theme.of(context).extension<MacrovaTokens>() ??
        MacrovaTokens.light;
    if (_remoteResults.isEmpty && _remoteLoading) {
      return const Center(
        child: EmptyState.loading(label: 'Searching USDA…'),
      );
    }
    if (_remoteResults.isEmpty && !_remoteLoading) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(MacrovaSpacing.xxl),
          child: Text(
            _searchCtrl.text.trim().isEmpty
                ? 'Type a food name to search USDA'
                : 'No matches — try different keywords',
            style: MacrovaTypography.bodyMedium(tokens.inkTertiary),
            textAlign: TextAlign.center,
          ),
        ),
      );
    }
    return ListView.separated(
      padding: const EdgeInsets.all(MacrovaSpacing.lg),
      itemCount: _remoteResults.length,
      separatorBuilder: (_, __) => const SizedBox(height: MacrovaSpacing.sm),
      itemBuilder: (_, i) {
        final item = _remoteResults[i];
        final busy = _resolvingFdcId == item.fdcId;
        return _RemoteResultCard(
          item: item,
          busy: busy,
          tokens: tokens,
          onTap: busy ? null : () => _resolveAndAdd(item),
        );
      },
    );
  }

  Widget _buildFilterTabs() {
    return Wrap(
      spacing: MacrovaSpacing.sm,
      runSpacing: MacrovaSpacing.sm,
      children: [
        MacrovaChip(
          label: 'Remote (USDA)',
          selected: _remoteUsdaMode,
          onTap: () {
            if (_remoteUsdaMode) {
              _leaveRemoteMode();
              setState(() {});
            } else {
              _enterRemoteMode();
            }
          },
        ),
        MacrovaChip(
          label: 'All',
          selected: !_remoteUsdaMode && _sourceFilter == null,
          onTap: () {
            _leaveRemoteMode();
            setState(() => _sourceFilter = null);
          },
        ),
        MacrovaChip(
          label: 'Saved',
          selected: !_remoteUsdaMode && _sourceFilter == IngredientSource.saved,
          onTap: () {
            _leaveRemoteMode();
            setState(() => _sourceFilter = IngredientSource.saved);
          },
        ),
        MacrovaChip(
          label: 'API',
          selected: !_remoteUsdaMode && _sourceFilter == IngredientSource.api,
          onTap: () {
            _leaveRemoteMode();
            setState(() => _sourceFilter = IngredientSource.api);
          },
        ),
        MacrovaChip(
          label: 'Custom',
          selected:
              !_remoteUsdaMode && _sourceFilter == IngredientSource.custom,
          onTap: () {
            _leaveRemoteMode();
            setState(() => _sourceFilter = IngredientSource.custom);
          },
        ),
      ],
    );
  }

  Widget _buildDetailPanel(BuildContext context, Ingredient ing) {
    final tokens = Theme.of(context).extension<MacrovaTokens>() ??
        MacrovaTokens.light;
    final goalsJson =
        context.watch<ProfileProvider>().profile.micronutrientGoals.toJson();

    return SingleChildScrollView(
      padding: const EdgeInsets.all(MacrovaSpacing.xlAlt),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SectionHeader(title: ing.name),
          MacroDisplay(
            calories: ing.caloriesPer100g,
            proteinG: ing.proteinPer100g,
            carbsG: ing.carbsPer100g,
            fatG: ing.fatPer100g,
          ),
          const SizedBox(height: MacrovaSpacing.sm),
          Text(
            'per 100g',
            style: MacrovaTypography.caption(tokens.inkTertiary),
          ),
          if (ing.micronutrientsPer100g.isNotEmpty) ...[
            const SizedBox(height: MacrovaSpacing.xlAlt),
            Text(
              'Micronutrients (per 100g)',
              style: MacrovaTypography.titleSm(tokens.inkPrimary),
            ),
            const SizedBox(height: MacrovaSpacing.sm),
            ..._micronutrientEntriesInDisplayOrder(ing.micronutrientsPer100g)
                .map((e) {
              final target = (goalsJson[e.key] as num?)?.toDouble() ?? 0;
              return MicronutrientBar(
                label: micronutrientLabelForKey(e.key),
                value: e.value,
                target: target,
                unit: micronutrientUnitForKey(e.key),
                isLimit: micronutrientIsLimitKey(e.key),
              );
            }),
          ],
          const SizedBox(height: MacrovaSpacing.xlAlt),
          Row(
            children: [
              FilledButton.icon(
                onPressed: () {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                        content:
                            Text('Navigate to Recipe Builder to add')),
                  );
                },
                icon: const Icon(Icons.add),
                label: const Text('Add to Recipe'),
              ),
              const SizedBox(width: MacrovaSpacing.sm),
              OutlinedButton(
                onPressed: () {
                  showDialog<void>(
                    context: context,
                    builder: (ctx) => _CreateIngredientDialog(
                      initial: ing,
                      onSave: (updated) {
                        context
                            .read<IngredientProvider>()
                            .updateIngredient(updated);
                      },
                    ),
                  );
                },
                child: const Text('Edit'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

/// Token-styled USDA remote search result row (tap to resolve & save).
class _RemoteResultCard extends StatelessWidget {
  final IngredientSearchResultItem item;
  final bool busy;
  final MacrovaTokens tokens;
  final VoidCallback? onTap;

  const _RemoteResultCard({
    required this.item,
    required this.busy,
    required this.tokens,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: MacrovaRadius.borderMd,
        child: Ink(
          decoration: BoxDecoration(
            color: tokens.surfaceTint,
            borderRadius: MacrovaRadius.borderMd,
            border: Border.all(color: tokens.lineDefault),
          ),
          child: Padding(
            padding: const EdgeInsets.all(MacrovaSpacing.md),
            child: Row(
              children: [
                Icon(
                  Icons.cloud_download_outlined,
                  size: 20,
                  color: tokens.inkTertiary,
                ),
                const SizedBox(width: MacrovaSpacing.md),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        item.description,
                        style: MacrovaTypography.bodyMedium(tokens.inkPrimary),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        'FDC ${item.fdcId} · tap to resolve & save',
                        style: MacrovaTypography.caption(tokens.inkTertiary),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: MacrovaSpacing.sm),
                busy
                    ? SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: tokens.accent,
                          backgroundColor: tokens.lineSoft,
                        ),
                      )
                    : Icon(
                        Icons.add_circle_outline,
                        size: 20,
                        color: tokens.accent,
                      ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _CreateIngredientDialog extends StatefulWidget {
  final Ingredient? initial;
  final ValueChanged<Ingredient> onSave;

  const _CreateIngredientDialog({this.initial, required this.onSave});

  @override
  State<_CreateIngredientDialog> createState() =>
      _CreateIngredientDialogState();
}

class _CreateIngredientDialogState extends State<_CreateIngredientDialog> {
  final _nameCtrl = TextEditingController();
  final _caloriesCtrl = TextEditingController();
  final _proteinCtrl = TextEditingController();
  final _carbsCtrl = TextEditingController();
  final _fatCtrl = TextEditingController();
  final _gramsPerCupCtrl = TextEditingController();
  final _gramsPerTbspCtrl = TextEditingController();
  final _customUnitCtrl = TextEditingController();

  final List<MapEntry<String, TextEditingController>> _microRows = [];

  @override
  void initState() {
    super.initState();
    final ing = widget.initial;
    if (ing != null) {
      _nameCtrl.text = ing.name;
      _caloriesCtrl.text = ing.caloriesPer100g.toStringAsFixed(0);
      _proteinCtrl.text = ing.proteinPer100g.toStringAsFixed(1);
      _carbsCtrl.text = ing.carbsPer100g.toStringAsFixed(1);
      _fatCtrl.text = ing.fatPer100g.toStringAsFixed(1);
      final cup = ing.unitConversions['cup'];
      if (cup != null) _gramsPerCupCtrl.text = cup.toStringAsFixed(0);
      final tbsp = ing.unitConversions['tbsp'];
      if (tbsp != null) _gramsPerTbspCtrl.text = tbsp.toStringAsFixed(0);

      for (final e in ing.micronutrientsPer100g.entries) {
        _microRows.add(MapEntry(
          e.key,
          TextEditingController(text: e.value.toStringAsFixed(2)),
        ));
      }
    }
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _caloriesCtrl.dispose();
    _proteinCtrl.dispose();
    _carbsCtrl.dispose();
    _fatCtrl.dispose();
    _gramsPerCupCtrl.dispose();
    _gramsPerTbspCtrl.dispose();
    _customUnitCtrl.dispose();
    for (final row in _microRows) {
      row.value.dispose();
    }
    super.dispose();
  }

  void _addMicroRow() {
    setState(() {
      _microRows.add(MapEntry('', TextEditingController()));
    });
  }

  void _save() {
    final name = _nameCtrl.text.trim();
    if (name.isEmpty) return;

    final conversions = <String, double>{};
    final cup = double.tryParse(_gramsPerCupCtrl.text.trim());
    if (cup != null && cup > 0) conversions['cup'] = cup;
    final tbsp = double.tryParse(_gramsPerTbspCtrl.text.trim());
    if (tbsp != null && tbsp > 0) conversions['tbsp'] = tbsp;
    final custom = double.tryParse(_customUnitCtrl.text.trim());
    if (custom != null && custom > 0) conversions['custom'] = custom;

    final micros = <String, double>{};
    for (final row in _microRows) {
      final key = row.key.trim();
      final val = double.tryParse(row.value.text.trim());
      if (key.isNotEmpty && val != null) {
        micros[key] = val;
      }
    }

    final ingredient = Ingredient(
      id: widget.initial?.id ?? _uuid.v4(),
      name: name,
      caloriesPer100g:
          double.tryParse(_caloriesCtrl.text.trim()) ?? 0,
      proteinPer100g:
          double.tryParse(_proteinCtrl.text.trim()) ?? 0,
      carbsPer100g: double.tryParse(_carbsCtrl.text.trim()) ?? 0,
      fatPer100g: double.tryParse(_fatCtrl.text.trim()) ?? 0,
      micronutrientsPer100g: micros,
      unitConversions: conversions,
      source: widget.initial?.source ?? IngredientSource.custom,
    );

    widget.onSave(ingredient);
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(
          widget.initial != null ? 'Edit Ingredient' : 'Create Custom Ingredient'),
      content: SizedBox(
        width: 400,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              TextField(
                controller: _nameCtrl,
                decoration: const InputDecoration(labelText: 'Name'),
              ),
              const SizedBox(height: 16),
              Text('Macros (per 100g)',
                  style: Theme.of(context).textTheme.titleSmall),
              const SizedBox(height: 8),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _caloriesCtrl,
                      decoration:
                          const InputDecoration(labelText: 'Calories (kcal)'),
                      keyboardType: TextInputType.number,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: TextField(
                      controller: _proteinCtrl,
                      decoration:
                          const InputDecoration(labelText: 'Protein (g)'),
                      keyboardType: TextInputType.number,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _carbsCtrl,
                      decoration:
                          const InputDecoration(labelText: 'Carbs (g)'),
                      keyboardType: TextInputType.number,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: TextField(
                      controller: _fatCtrl,
                      decoration: const InputDecoration(labelText: 'Fat (g)'),
                      keyboardType: TextInputType.number,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Text('Micronutrients',
                      style: Theme.of(context).textTheme.titleSmall),
                  const Spacer(),
                  TextButton.icon(
                    onPressed: _addMicroRow,
                    icon: const Icon(Icons.add, size: 18),
                    label: const Text('Add Row'),
                  ),
                ],
              ),
              ..._microRows.asMap().entries.map((entry) {
                final i = entry.key;
                final row = entry.value;
                return Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Row(
                    children: [
                      Expanded(
                        flex: 2,
                        child: TextField(
                          decoration:
                              const InputDecoration(hintText: 'Key (e.g. iron_mg)'),
                          controller: TextEditingController(text: row.key),
                          onChanged: (v) {
                            _microRows[i] = MapEntry(v, row.value);
                          },
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: TextField(
                          controller: row.value,
                          decoration:
                              const InputDecoration(hintText: 'Value'),
                          keyboardType: TextInputType.number,
                        ),
                      ),
                    ],
                  ),
                );
              }),
              const SizedBox(height: 16),
              Text('Unit Conversions',
                  style: Theme.of(context).textTheme.titleSmall),
              const SizedBox(height: 8),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _gramsPerCupCtrl,
                      decoration:
                          const InputDecoration(labelText: 'Grams per cup'),
                      keyboardType: TextInputType.number,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: TextField(
                      controller: _gramsPerTbspCtrl,
                      decoration:
                          const InputDecoration(labelText: 'Grams per tbsp'),
                      keyboardType: TextInputType.number,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _customUnitCtrl,
                decoration:
                    const InputDecoration(labelText: 'Custom unit (g)'),
                keyboardType: TextInputType.number,
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: _save,
          child: const Text('Save Ingredient'),
        ),
      ],
    );
  }
}
