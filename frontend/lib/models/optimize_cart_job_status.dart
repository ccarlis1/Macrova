/// Response from `GET /api/v1/grocery/optimize-cart/{jobId}`.
class OptimizeCartJobStatus {
  const OptimizeCartJobStatus({
    required this.status,
    required this.progress,
    required this.stage,
    this.result,
    this.error,
    this.stats,
  });

  final String status;
  final int progress;
  final String stage;
  final Map<String, dynamic>? result;
  final OptimizeCartSerializedError? error;
  final OptimizeCartJobStats? stats;

  bool get isQueued => status == 'queued';
  bool get isRunning => status == 'running';
  bool get isCompleted => status == 'completed';
  bool get isFailed => status == 'failed';

  bool get isTerminal => isCompleted || isFailed;

  factory OptimizeCartJobStatus.fromJson(Map<String, dynamic> json) {
    OptimizeCartSerializedError? err;
    final rawErr = json['error'];
    if (rawErr is Map<String, dynamic>) {
      err = OptimizeCartSerializedError.fromJson(rawErr);
    }
    OptimizeCartJobStats? st;
    final rawSt = json['stats'];
    if (rawSt is Map<String, dynamic>) {
      st = OptimizeCartJobStats.fromJson(rawSt);
    }
    Map<String, dynamic>? res;
    final rawRes = json['result'];
    if (rawRes is Map<String, dynamic>) {
      res = rawRes;
    }
    return OptimizeCartJobStatus(
      status: json['status'] as String? ?? 'unknown',
      progress: (json['progress'] as num?)?.round() ?? 0,
      stage: json['stage'] as String? ?? '',
      result: res,
      error: err,
      stats: st,
    );
  }
}

class OptimizeCartSerializedError {
  const OptimizeCartSerializedError({
    required this.message,
    this.code,
    this.retryable = false,
  });

  final String message;
  final String? code;
  final bool retryable;

  factory OptimizeCartSerializedError.fromJson(Map<String, dynamic> json) {
    return OptimizeCartSerializedError(
      message: json['message'] as String? ?? 'Unknown error',
      code: json['code'] as String?,
      retryable: json['retryable'] == true,
    );
  }
}

class OptimizeCartJobStats {
  const OptimizeCartJobStats({
    required this.runId,
    required this.totalLatency,
    required this.searchLatency,
    required this.failedQueries,
    required this.cacheHits,
  });

  final String runId;
  final int totalLatency;
  final int searchLatency;
  final int failedQueries;
  final int cacheHits;

  factory OptimizeCartJobStats.fromJson(Map<String, dynamic> json) {
    return OptimizeCartJobStats(
      runId: json['runId'] as String? ?? '',
      totalLatency: (json['totalLatency'] as num?)?.round() ?? 0,
      searchLatency: (json['searchLatency'] as num?)?.round() ?? 0,
      failedQueries: (json['failedQueries'] as num?)?.round() ?? 0,
      cacheHits: (json['cacheHits'] as num?)?.round() ?? 0,
    );
  }
}
