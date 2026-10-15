/**
 * Example JavaScript client untuk autentikasi dan chat dengan API
 * 
 * Usage di Node.js:
 *   node examples/javascript_client.js
 * 
 * Usage di Browser:
 *   <script src="javascript_client.js"></script>
 *   <script>
 *     const client = new IPPLChatbotClient('http://localhost:8000');
 *     await client.login('dev', 'dev');
 *     const userInfo = await client.getMe();
 *   </script>
 */

class IPPLChatbotClient {
  /**
   * Client untuk IPPL Chatbot API dengan auto-refresh token
   * @param {string} baseUrl - Base URL of API (default: http://localhost:8000)
   */
  constructor(baseUrl = 'http://localhost:8000') {
    this.baseUrl = baseUrl;
    this.accessToken = null;
    this.refreshToken = null;
    this.expiresAt = null;
  }

  /**
   * Login dengan username dan password
   * @param {string} username - Username Keycloak
   * @param {string} password - Password
   * @returns {Promise<object>} Token response
   */
  async login(username, password) {
    const response = await fetch(`${this.baseUrl}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(`Login failed: ${error.detail}`);
    }

    const data = await response.json();
    this.accessToken = data.access_token;
    this.refreshToken = data.refresh_token;
    this.expiresAt = new Date(Date.now() + data.expires_in * 1000);

    console.log(`✅ Login successful as '${username}'`);
    console.log(`   Token expires at: ${this.expiresAt.toLocaleString()}`);

    return data;
  }

  /**
   * Refresh access token
   * @returns {Promise<object>} Token response
   */
  async refresh() {
    if (!this.refreshToken) {
      throw new Error('No refresh token available. Please login first.');
    }

    const response = await fetch(`${this.baseUrl}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: this.refreshToken })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(`Token refresh failed: ${error.detail}`);
    }

    const data = await response.json();
    this.accessToken = data.access_token;
    this.refreshToken = data.refresh_token;
    this.expiresAt = new Date(Date.now() + data.expires_in * 1000);

    console.log('🔄 Token refreshed');
    console.log(`   New token expires at: ${this.expiresAt.toLocaleString()}`);

    return data;
  }

  /**
   * Pastikan access token masih valid
   */
  async ensureTokenValid() {
    if (!this.accessToken) {
      throw new Error('Not logged in. Please call login() first.');
    }

    // Refresh jika akan expired dalam 1 menit
    const oneMinuteFromNow = new Date(Date.now() + 60000);
    if (this.expiresAt && this.expiresAt <= oneMinuteFromNow) {
      await this.refresh();
    }
  }

  /**
   * Get headers dengan Authorization Bearer token
   * @returns {object} Headers
   */
  getHeaders() {
    if (!this.accessToken) {
      throw new Error('Not logged in. Please call login() first.');
    }
    return { Authorization: `Bearer ${this.accessToken}` };
  }

  /**
   * Get informasi user yang sedang login
   * @returns {Promise<object>} User info
   */
  async getMe() {
    await this.ensureTokenValid();

    const response = await fetch(`${this.baseUrl}/me`, {
      headers: this.getHeaders()
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(`Get user info failed: ${error.detail}`);
    }

    return response.json();
  }

  /**
   * Chat dengan LLM
   * @param {string} prompt - Pertanyaan atau pesan
   * @returns {Promise<object>} Response dari LLM
   */
  async chat(prompt) {
    await this.ensureTokenValid();

    const response = await fetch(`${this.baseUrl}/llm/chat`, {
      method: 'POST',
      headers: {
        ...this.getHeaders(),
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ prompt })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(`Chat failed: ${error.detail}`);
    }

    return response.json();
  }

  /**
   * Logout dan revoke refresh token
   */
  async logout() {
    if (!this.refreshToken) {
      console.log('⚠️  Not logged in');
      return;
    }

    await fetch(`${this.baseUrl}/auth/logout`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: this.refreshToken })
    });

    this.accessToken = null;
    this.refreshToken = null;
    this.expiresAt = null;

    console.log('👋 Logged out successfully');
  }

  /**
   * Save tokens ke localStorage (browser only)
   */
  saveToLocalStorage() {
    if (typeof localStorage === 'undefined') {
      throw new Error('localStorage not available');
    }

    localStorage.setItem('ippl_access_token', this.accessToken);
    localStorage.setItem('ippl_refresh_token', this.refreshToken);
    localStorage.setItem('ippl_expires_at', this.expiresAt.toISOString());
  }

  /**
   * Load tokens dari localStorage (browser only)
   */
  loadFromLocalStorage() {
    if (typeof localStorage === 'undefined') {
      throw new Error('localStorage not available');
    }

    this.accessToken = localStorage.getItem('ippl_access_token');
    this.refreshToken = localStorage.getItem('ippl_refresh_token');
    const expiresAt = localStorage.getItem('ippl_expires_at');
    this.expiresAt = expiresAt ? new Date(expiresAt) : null;
  }

  /**
   * Clear tokens dari localStorage (browser only)
   */
  clearLocalStorage() {
    if (typeof localStorage === 'undefined') {
      throw new Error('localStorage not available');
    }

    localStorage.removeItem('ippl_access_token');
    localStorage.removeItem('ippl_refresh_token');
    localStorage.removeItem('ippl_expires_at');
  }
}

// Example usage (Node.js)
async function main() {
  const client = new IPPLChatbotClient('http://localhost:8000');

  console.log('='.repeat(60));
  console.log('IPPL Chatbot JavaScript Client Example');
  console.log('='.repeat(60));
  console.log();

  try {
    // 1. Login
    console.log('1️⃣  Login...');
    await client.login('dev', 'dev');
    console.log();

    // 2. Get user info
    console.log('2️⃣  Get user info...');
    const userInfo = await client.getMe();
    console.log(`   Username: ${userInfo.username}`);
    console.log(`   Email: ${userInfo.email}`);
    console.log(`   Full name: ${userInfo.full_name}`);
    console.log(`   Roles: ${userInfo.roles.slice(0, 3).join(', ')}...`);
    console.log();

    // 3. Chat with LLM
    console.log('3️⃣  Chat with LLM...');
    const questions = [
      'Siapa kamu?',
      'Apa itu JavaScript?',
      'Jelaskan JWT dalam 1 kalimat'
    ];

    for (let i = 0; i < questions.length; i++) {
      const question = questions[i];
      console.log(`\n   Q${i + 1}: ${question}`);
      try {
        const response = await client.chat(question);
        let answer = response.answer;
        // Truncate long answers
        if (answer.length > 150) {
          answer = answer.substring(0, 150) + '...';
        }
        console.log(`   A${i + 1}: ${answer}`);
      } catch (error) {
        console.log(`   ⚠️  Error: ${error.message}`);
      }
    }

    console.log();

    // 4. Test token refresh
    console.log('4️⃣  Test token refresh...');
    await client.refresh();
    console.log();

    // 5. Verify new token works
    console.log('5️⃣  Verify new token...');
    const userInfo2 = await client.getMe();
    console.log(`   ✅ New token works! Still logged in as ${userInfo2.username}`);
    console.log();

    // 6. Logout
    console.log('6️⃣  Logout...');
    await client.logout();

  } catch (error) {
    console.error('❌ Error:', error.message);
  }

  console.log();
  console.log('='.repeat(60));
  console.log('Done!');
  console.log('='.repeat(60));
}

// Run if executed directly (Node.js)
if (typeof require !== 'undefined' && require.main === module) {
  main().catch(console.error);
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = IPPLChatbotClient;
}
