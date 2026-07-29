import Foundation

enum APIResult<T: Sendable>: Sendable {
    case success(T)
    case failure(APIError)
}

struct APIError: Error, LocalizedError, Sendable {
    let message: String
    let status: Int?
    let code: String?

    var errorDescription: String? { message }

    static func http(status: Int, body: Data?) -> APIError {
        var message = "HTTP \(status)"
        if let body, let obj = try? JSONSerialization.jsonObject(with: body) as? [String: Any] {
            if let detail = obj["detail"] as? String { message = detail }
            else if let msg = obj["message"] as? String { message = msg }
        }
        let code: String
        switch status {
        case 400, 422: code = "validation_error"
        case 401: code = "unauthorized"
        case 403: code = "forbidden"
        case 404: code = "not_found"
        case 429: code = "rate_limited"
        default: code = status >= 500 ? "server_error" : "http_error"
        }
        return APIError(message: message, status: status, code: code)
    }
}
