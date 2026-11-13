import SwiftUI

struct RootView: View {
    @EnvironmentObject private var session: DearTGSession

    var body: some View {
        Group {
            if session.token == nil {
                AuthView()
            } else {
                ChatListView()
            }
        }
        .tint(Color(red: 0.40, green: 0.82, blue: 0.72))
        .alert("DearTG", isPresented: Binding(
            get: { session.error != nil },
            set: { if !$0 { session.error = nil } }
        )) {
            Button("ОК") { session.error = nil }
        } message: {
            Text(session.error ?? "")
        }
    }
}

struct AuthView: View {
    @EnvironmentObject private var session: DearTGSession
    @State private var username = ""
    @State private var password = ""
    @State private var isRegister = true

    var body: some View {
        VStack(spacing: 22) {
            Spacer()
            ZStack {
                RoundedRectangle(cornerRadius: 28).fill(Color(red: 0.18, green: 0.42, blue: 0.39))
                    .frame(width: 92, height: 92)
                Image(systemName: "bubble.left.and.bubble.right.fill")
                    .font(.system(size: 38, weight: .semibold)).foregroundStyle(.white)
            }
            Text("DearTG").font(.system(size: 36, weight: .bold, design: .rounded))
            Text("Твои сообщения. Твои правила.").foregroundStyle(.secondary)
            VStack(spacing: 12) {
                TextField("Имя пользователя", text: $username)
                    .textInputAutocapitalization(.never).autocorrectionDisabled()
                    .textFieldStyle(.roundedBorder)
                SecureField("Пароль (минимум 10 символов)", text: $password)
                    .textFieldStyle(.roundedBorder)
                Button {
                    Task { await session.authenticate(username: username, password: password, register: isRegister) }
                } label: {
                    HStack {
                        if session.isBusy { ProgressView().tint(.white) }
                        Text(isRegister ? "Создать аккаунт" : "Войти")
                    }.frame(maxWidth: .infinity).padding(.vertical, 13)
                }
                .buttonStyle(.borderedProminent).disabled(session.isBusy || username.count < 3 || password.count < 10)
                Button(isRegister ? "Уже есть аккаунт? Войти" : "Новый пользователь? Регистрация") {
                    isRegister.toggle()
                }.font(.footnote)
            }
            .padding(.horizontal, 28)
            Spacer()
            VStack(alignment: .leading, spacing: 6) {
                Text("Адрес локального сервера").font(.caption).foregroundStyle(.secondary)
                TextField("http://192.168.1.100:8080", text: $session.serverURL)
                    .textInputAutocapitalization(.never).autocorrectionDisabled()
                    .keyboardType(.URL).textFieldStyle(.roundedBorder)
            }.padding(.horizontal, 28).padding(.bottom, 20)
        }
        .background(Color(uiColor: .systemBackground))
    }
}

struct ChatListView: View {
    @EnvironmentObject private var session: DearTGSession
    @State private var showingCreate = false
    @State private var title = ""

    var body: some View {
        NavigationStack {
            List(session.chats) { chat in
                NavigationLink {
                    ConversationView(chat: chat)
                } label: {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(chat.title).font(.headline)
                        Text(chat.lastMessage ?? "Начните общение")
                            .font(.subheadline).foregroundStyle(.secondary).lineLimit(1)
                    }.padding(.vertical, 4)
                }
            }
            .overlay {
                if session.chats.isEmpty {
                    ContentUnavailableView("Пока нет чатов", systemImage: "bubble.left.and.bubble.right",
                                           description: Text("Создай чат и пригласи собеседника"))
                }
            }
            .navigationTitle("DearTG")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button { session.logout() } label: { Image(systemName: "rectangle.portrait.and.arrow.right") }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button { showingCreate = true } label: { Image(systemName: "plus") }
                }
            }
            .refreshable { await session.loadChats() }
            .task {
                while !Task.isCancelled {
                    await session.loadChats()
                    try? await Task.sleep(for: .seconds(5))
                }
            }
            .alert("Новый чат", isPresented: $showingCreate) {
                TextField("Название", text: $title)
                Button("Создать") {
                    let value = title.trimmingCharacters(in: .whitespacesAndNewlines)
                    guard !value.isEmpty else { return }
                    Task { await session.createChat(title: value) }
                    title = ""
                }
                Button("Отмена", role: .cancel) { title = "" }
            }
        }
    }
}

struct ConversationView: View {
    @EnvironmentObject private var session: DearTGSession
    let chat: Chat
    @State private var messages: [Message] = []
    @State private var draft = ""
    @State private var inviteName = ""
    @State private var showingInvite = false

    var body: some View {
        VStack(spacing: 0) {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(spacing: 10) {
                        ForEach(messages) { message in
                            HStack {
                                if message.senderId == session.user?.id { Spacer(minLength: 50) }
                                Text(message.body)
                                    .padding(11)
                                    .background(message.senderId == session.user?.id
                                                ? Color.green.opacity(0.22) : Color.secondary.opacity(0.16))
                                    .clipShape(RoundedRectangle(cornerRadius: 16))
                                if message.senderId != session.user?.id { Spacer(minLength: 50) }
                            }.id(message.id)
                        }
                    }.padding()
                }
                .onChange(of: messages.count) { _, _ in
                    if let last = messages.last { proxy.scrollTo(last.id, anchor: .bottom) }
                }
            }
            HStack(spacing: 10) {
                TextField("Сообщение", text: $draft, axis: .vertical).lineLimit(1...4)
                    .textFieldStyle(.roundedBorder)
                Button {
                    let value = draft.trimmingCharacters(in: .whitespacesAndNewlines)
                    guard !value.isEmpty else { return }
                    draft = ""
                    Task {
                        do { try await session.send(value, to: chat); await refresh() }
                        catch { session.error = error.localizedDescription }
                    }
                } label: { Image(systemName: "arrow.up.circle.fill").font(.system(size: 30)) }
            }.padding()
        }
        .navigationTitle(chat.title).navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button { showingInvite = true } label: { Image(systemName: "person.badge.plus") }
            }
        }
        .task {
            while !Task.isCancelled {
                await refresh()
                try? await Task.sleep(for: .seconds(3))
            }
        }
        .alert("Пригласить пользователя", isPresented: $showingInvite) {
            TextField("Username", text: $inviteName)
                .textInputAutocapitalization(.never)
            Button("Добавить") {
                let name = inviteName.trimmingCharacters(in: .whitespacesAndNewlines)
                Task {
                    do { try await session.invite(username: name, to: chat); await refresh() }
                    catch { session.error = error.localizedDescription }
                }
                inviteName = ""
            }
            Button("Отмена", role: .cancel) { inviteName = "" }
        }
    }

    private func refresh() async {
        do { messages = try await session.messages(in: chat) }
        catch { session.error = error.localizedDescription }
    }
}
