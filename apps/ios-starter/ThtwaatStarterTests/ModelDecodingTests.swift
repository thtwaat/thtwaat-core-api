import Foundation
import XCTest
@testable import ThtwaatStarter

final class ModelDecodingTests: XCTestCase {
    func testTokenResponseDecoding() throws {
        let json = """
        {"access_token":"acc","refresh_token":"ref","token_type":"bearer","expires_in":3600}
        """.data(using: .utf8)!
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let tokens = try decoder.decode(TokenResponse.self, from: json)
        XCTAssertEqual(tokens.accessToken, "acc")
        XCTAssertEqual(tokens.refreshToken, "ref")
    }

    func testChatResponseFallbackText() throws {
        let json = """
        {"response":"Hello","conversation_id":"c1","suggested_prompts":["A","B"]}
        """.data(using: .utf8)!
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let chat = try decoder.decode(ChatResponse.self, from: json)
        XCTAssertEqual(chat.text, "Hello")
        XCTAssertEqual(chat.conversationId, "c1")
        XCTAssertEqual(chat.suggestedPrompts?.count, 2)
    }

    func testTemplateItemDecoding() throws {
        let json = """
        {"id":"1","slug":"ai-website-starter","name":"AI Website","category":"website","description":"d","version":"1.0.0"}
        """.data(using: .utf8)!
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let item = try decoder.decode(TemplateItem.self, from: json)
        XCTAssertEqual(item.slug, "ai-website-starter")
    }

    func testWidgetConfigDecoding() throws {
        let json = """
        {"agent_id":"a1","widget_id":"w1","status":"PUBLISHED","config":{"theme":"light","primary_color":"#111","welcome_message":"Hi"}}
        """.data(using: .utf8)!
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let widget = try decoder.decode(WidgetConfigResponse.self, from: json)
        XCTAssertEqual(widget.widgetId, "w1")
        XCTAssertEqual(widget.config?.welcomeMessage, "Hi")
    }
}
