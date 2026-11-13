import Foundation

struct User: Codable, Identifiable {
    let id: Int
    let username: String
}

struct Chat: Codable, Identifiable {
    let id: Int
    let title: String
    let createdAt: Int
    var lastMessage: String?
}

struct Message: Codable, Identifiable {
    let id: Int
    let chatId: Int
    let senderId: Int
    let body: String
    let createdAt: Int
}

enum APIError: LocalizedError {
    case invalidResponse
    case server(String)

    var errorDescription: String? {
        switch self {
        case .invalidResponse: return "Сервер вернул некорректный ответ"
        case let .server(message): return message
        }
    }
}

@MainActor
final class DearTGSession: ObservableObject {
    @Published var token: String?
    @Published var user: User?
    @Published var chats: [Chat] = []
    @Published var error: String?
    @Published var isBusy = false
    @Published var serverURL: String {
        didSet { UserDefaults.standard.set(serverURL, forKey: "deartg.serverURL") }
    }

    private let defaults = UserDefaults.standard
    private var decoder: JSONDecoder {
        let value = JSONDecoder()
        value.keyDecodingStrategy = .convertFromSnakeCase
        return value
    }
    private var encoder: JSONEncoder {
        let value = JSONEncoder()
        value.keyEncodingStrategy = .convertToSnakeCase
        return value
    }

    init() {
        self.serverURL = defaults.string(forKey: "deartg.serverURL") ?? "http://192.168.1.100:8080"
        self.token = defaults.string(forKey: "deartg.token")
        if token != nil {
            Task { await loadMeAndChats() }
        }
    }

    private func request<T: Decodable>(_ path: String, method: String = "GET",
                                        body: Encodable? = nil,
                                        query: [URLQueryItem] = []) async throws -> T {
        guard var components = URLComponents(string: serverURL.trimmingCharacters(in: CharacterSet(charactersIn: "/")) + path) else {
            throw APIError.server("Проверь адрес сервера")
        }
        if !query.isEmpty { components.queryItems = query }
        guard let url = components.url else { throw APIError.invalidResponse }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let token { request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        if let body { request.httpBody = try encoder.encode(AnyEncodable(body)) }
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200..<300).contains(http.statusCode) else {
            let payload = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
            throw APIError.server(payload?["detail"] as? String ?? "Ошибка сервера (\(http.statusCode))")
        }
        return try decoder.decode(T.self, from: data)
    }

    func authenticate(username: String, password: String, register: Bool) async {
        isBusy = true
        error = nil
        defer { isBusy = false }
        do {
            let result: AuthResult = try await request(register ? "/v1/auth/register" : "/v1/auth/login",
                                                        method: "POST",
                                                        body: Credentials(username: username, password: password))
            token = result.accessToken
            user = result.user
            defaults.set(result.accessToken, forKey: "deartg.token")
            await loadChats()
        } catch { self.error = error.localizedDescription }
    }

    func loadMeAndChats() async {
        do {
            let me: User = try await request("/v1/me")
            user = me
            await loadChats()
        } catch {
            logout()
            self.error = error.localizedDescription
        }
    }

    func loadChats() async {
        do { chats = try await request("/v1/chats") }
        catch { self.error = error.localizedDescription }
    }

    func createChat(title: String) async {
        do {
            let _: Chat = try await request("/v1/chats", method: "POST", body: ChatPayload(title: title))
            await loadChats()
        } catch { error = error.localizedDescription }
    }

    func invite(username: String, to chat: Chat) async throws {
        let _: MemberResult = try await request("/v1/chats/\(chat.id)/members", method: "POST",
            query: [URLQueryItem(name: "username", value: username)])
    }

    func messages(in chat: Chat) async throws -> [Message] {
        try await request("/v1/chats/\(chat.id)/messages")
    }

    func send(_ text: String, to chat: Chat) async throws {
        let _: Message = try await request("/v1/chats/\(chat.id)/messages", method: "POST",
                                           body: MessagePayload(body: text))
    }

    func logout() {
        token = nil
        user = nil
        chats = []
        defaults.removeObject(forKey: "deartg.token")
    }
}

private struct AuthResult: Decodable {
    let accessToken: String
    let user: User
}
private struct Credentials: Encodable { let username: String; let password: String }
private struct ChatPayload: Encodable { let title: String }
private struct MessagePayload: Encodable { let body: String }
private struct MemberResult: Decodable { let chatId: Int; let user: User }

private struct AnyEncodable: Encodable {
    private let encodeValue: (Encoder) throws -> Void
    init<T: Encodable>(_ value: T) { encodeValue = value.encode }
    func encode(to encoder: Encoder) throws { try encodeValue(encoder) }
}
