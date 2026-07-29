import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:thtwaat_flutter/thtwaat_flutter.dart';

void main() {
  group('ThtwaatClient', () {
    test('public chat works with api key', () async {
      final mock = MockClient((request) async {
        expect(request.url.path, '/public/v1/chat');
        return http.Response(jsonEncode({'reply': 'Hello back', 'conversation_id': 'conv_1'}), 200);
      });

      final client = ThtwaatClient(apiKey: 'tht_live_xxx', apiUrl: 'https://api.example.com', http: mock);
      final res = await client.chat.chat(const ChatRequest(message: 'Hello'));
      expect(res.reply, 'Hello back');
      expect(res.conversationId, 'conv_1');
    });

    test('login stores tokens', () async {
      final mock = MockClient((request) async {
        expect(request.url.path, '/api/v1/auth/login');
        return http.Response(jsonEncode({
          'access_token': 'acc',
          'refresh_token': 'ref',
          'token_type': 'bearer',
          'expires_in': 3600,
        }), 200);
      });
      final client = ThtwaatClient(apiUrl: 'https://api.example.com', http: mock);
      final tokens = await client.auth.login(const LoginRequest(email: 'a@b.com', password: 'secret'));
      expect(tokens.accessToken, 'acc');
      expect(client.accessToken, 'acc');
      expect(client.refreshToken, 'ref');
    });

    test('marketplace templates list parses', () async {
      final mock = MockClient((request) async {
        return http.Response(jsonEncode([
          {
            'id': '1',
            'slug': 'ai-website-starter',
            'name': 'AI Website Starter',
            'category': 'website',
            'description': 'desc',
            'version': '1.0.0',
            'tags': ['website']
          }
        ]), 200);
      });
      final client = ThtwaatClient(accessToken: 'jwt', apiUrl: 'https://api.example.com', http: mock);
      final items = await client.marketplace.templates();
      expect(items.single.slug, 'ai-website-starter');
    });

    test('product generator analyze parses', () async {
      final mock = MockClient((request) async {
        return http.Response(jsonEncode({
          'industry': 'restaurant',
          'product_type': 'website',
          'category': 'website',
          'required_features': ['ai_chat', 'ordering'],
          'brand_tone': 'friendly',
          'language': 'en',
          'suggested_name': 'Restaurant Website',
          'confidence': 0.9,
          'keywords_matched': ['restaurant', 'ordering']
        }), 200);
      });
      final client = ThtwaatClient(accessToken: 'jwt', apiUrl: 'https://api.example.com', http: mock);
      final out = await client.productGenerator.analyze('Restaurant website with AI ordering');
      expect(out.industry, 'restaurant');
      expect(out.requiredFeatures, contains('ordering'));
    });

    test('typed http error throws', () async {
      final mock = MockClient((request) async => http.Response(jsonEncode({'detail': 'Unauthorized'}), 401));
      final client = ThtwaatClient(apiUrl: 'https://api.example.com', http: mock);
      expect(
        () => client.auth.me(),
        throwsA(isA<ThtwaatException>().having((e) => e.status, 'status', 401)),
      );
    });
  });
}
