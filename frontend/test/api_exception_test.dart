import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:macrova/services/api_service.dart';

void main() {
  group('ApiException.fromResponse', () {
    test('parses structured error envelope', () {
      final res = http.Response(
        '{"error":{"code":"INVALID_REQUEST","message":"Bad"}}',
        400,
      );
      final e = ApiException.fromResponse(res);
      expect(e.statusCode, 400);
      expect(e.code, 'INVALID_REQUEST');
      expect(e.message, 'Bad');
    });

    test('parses FastAPI validation detail', () {
      final res = http.Response(
        '{"detail":[{"loc":["body","x"],"msg":"field required","type":"value_error.missing"}]}',
        422,
      );
      final e = ApiException.fromResponse(res);
      expect(e.statusCode, 422);
      expect(e.code, 'VALIDATION_ERROR');
      expect(e.message, 'field required');
    });

    test('fallback for non-json body', () {
      final res = http.Response('gone', 502);
      final e = ApiException.fromResponse(res);
      expect(e.statusCode, 502);
      expect(e.code, 'HTTP_ERROR');
      expect(e.message, 'gone');
    });

    test('empty body uses status in message', () {
      final res = http.Response('', 503);
      final e = ApiException.fromResponse(res);
      expect(e.code, 'HTTP_ERROR');
      expect(e.message, 'Request failed with status 503');
    });
  });
}
