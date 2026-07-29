import XCTest

final class ThtwaatStarterUITests: XCTestCase {
    func testLaunchShowsBrand() throws {
        let app = XCUIApplication()
        app.launch()
        XCTAssertTrue(app.staticTexts["THTWAAT"].waitForExistence(timeout: 5))
    }
}
