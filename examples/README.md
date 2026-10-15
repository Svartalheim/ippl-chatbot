# Client Examples

Contoh implementasi client untuk autentikasi dan chat dengan IPPL Chatbot API.

## 📁 Files

### 1. Python Client (`python_client.py`)

Client Python dengan auto-refresh token.

**Requirements:**
```bash
pip install httpx
```

**Usage:**
```bash
python examples/python_client.py
```

**Features:**
- ✅ Login dengan username/password
- ✅ Auto-refresh token sebelum expired
- ✅ Get user info
- ✅ Chat dengan LLM
- ✅ Logout

**Example:**
```python
from python_client import IPPLChatbotClient

client = IPPLChatbotClient("http://localhost:8000")
await client.login("dev", "dev")

user_info = await client.get_me()
print(f"Logged in as: {user_info['username']}")

response = await client.chat("Hello!")
print(response['answer'])

await client.logout()
```

---

### 2. JavaScript Client (`javascript_client.js`)

Client JavaScript/Node.js dengan support browser dan Node.js.

**Usage di Node.js:**
```bash
node examples/javascript_client.js
```

**Usage di Browser:**
```html
<script src="javascript_client.js"></script>
<script>
  const client = new IPPLChatbotClient('http://localhost:8000');
  await client.login('dev', 'dev');
  
  const userInfo = await client.getMe();
  console.log('Logged in as:', userInfo.username);
  
  const response = await client.chat('Hello!');
  console.log(response.answer);
  
  await client.logout();
</script>
```

**Features:**
- ✅ Login dengan username/password
- ✅ Auto-refresh token sebelum expired
- ✅ Get user info
- ✅ Chat dengan LLM
- ✅ Logout
- ✅ LocalStorage support (browser)

---

### 3. Browser Client (`browser_client.html`)

Full-featured web UI untuk testing autentikasi dan chat.

**Usage:**
```bash
# Option 1: Open directly in browser
open examples/browser_client.html

# Option 2: Serve with Python HTTP server
cd examples
python3 -m http.server 8080
# Then open http://localhost:8080/browser_client.html
```

**Features:**
- ✅ Login form
- ✅ User dashboard
- ✅ Real-time token expiry countdown
- ✅ Chat interface
- ✅ Responsive design
- ✅ Error handling

**Screenshots:**

Login:
```
┌─────────────────────────────┐
│      🤖 IPPL Chatbot       │
│                             │
│  Username: [dev          ]  │
│  Password: [****         ]  │
│                             │
│        [Login Button]       │
└─────────────────────────────┘
```

Chat:
```
┌─────────────────────────────┐
│      Dashboard              │
│  Status: ● Logged In        │
│  Username: dev              │
│  Token expires in: 4m 23s   │
└─────────────────────────────┘

┌─────────────────────────────┐
│      Chat with LLM          │
│                             │
│  You: Hello!                │
│                             │
│  Bot: Hi there! How can I   │
│       help you today?       │
│                             │
│  [Type message here...   ]  │
│  [Send Message]             │
└─────────────────────────────┘
```

---

## 🚀 Quick Start

### 1. Start the API

```bash
# From project root
make up

# Wait for services to be ready
make logs
```

### 2. Run Examples

**Python:**
```bash
pip install httpx
python examples/python_client.py
```

**JavaScript:**
```bash
node examples/javascript_client.js
```

**Browser:**
```bash
open examples/browser_client.html
```

---

## 🔑 Default Credentials

- **Username:** `dev`
- **Password:** `dev`
- **API URL:** `http://localhost:8000`
- **Keycloak URL:** `http://localhost:8080`

---

## 📚 Documentation

For complete authentication documentation, see [../docs/AUTHENTICATION.md](../docs/AUTHENTICATION.md)

---

## 💡 Tips

### Auto-Refresh Pattern

Semua client mengimplementasikan auto-refresh pattern:

```
1. Login → Get access_token + refresh_token
2. Use access_token for API calls
3. Before access_token expires (check sebelum 1 menit):
   - Call /auth/refresh with refresh_token
   - Get new access_token + refresh_token
4. Continue using new access_token
```

### Token Expiry

- **Access Token:** 5 menit (300 detik)
- **Refresh Token:** 30 menit (1800 detik)

Best practice: Refresh access token **1 menit sebelum expired**.

### Error Handling

Semua client handle common errors:

- `401 Unauthorized`: Token invalid/expired → Refresh or re-login
- `403 Forbidden`: Insufficient permissions → Check roles
- `503 Service Unavailable`: Keycloak/backend down → Retry later

### Security

**Browser clients:**
- ⚠️ Jangan simpan token di `localStorage` untuk production (vulnerable to XSS)
- ✅ Gunakan secure HTTP-only cookies
- ✅ Enable CORS dengan whitelist origins

**All clients:**
- ✅ Always use HTTPS di production
- ✅ Never log/expose tokens
- ✅ Implement proper logout (revoke refresh token)

---

## 🐛 Troubleshooting

### CORS Error (Browser)

Jika mendapat CORS error di browser:

1. Pastikan API running di `http://localhost:8000`
2. Tambahkan CORS middleware di FastAPI:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],  # Your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Connection Refused

Pastikan services running:

```bash
make up
docker compose ps
```

### Login Failed

Check Keycloak:

1. Buka http://localhost:8080
2. Login dengan admin/admin
3. Pilih realm "dev"
4. Check user "dev" ada dan enabled

---

## 🤝 Contributing

Feel free to add more client examples:

- React/Vue/Angular components
- Mobile apps (React Native, Flutter)
- Desktop apps (Electron, Tauri)
- CLI tools

Submit a PR with your example! 🎉
