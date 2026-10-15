"""
Example Python client untuk autentikasi dan chat dengan API

Install dependencies:
    pip install httpx

Usage:
    python examples/python_client.py
"""
import asyncio
import httpx
from datetime import datetime, timedelta
from typing import Optional


class IPPLChatbotClient:
    """Client untuk IPPL Chatbot API dengan auto-refresh token"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.expires_at: Optional[datetime] = None
    
    async def login(self, username: str, password: str) -> dict:
        """
        Login dengan username dan password
        
        Args:
            username: Username Keycloak
            password: Password
            
        Returns:
            dict: Token response dari API
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/auth/login",
                json={"username": username, "password": password}
            )
            response.raise_for_status()
            
            data = response.json()
            self.access_token = data["access_token"]
            self.refresh_token = data["refresh_token"]
            self.expires_at = datetime.now() + timedelta(seconds=data["expires_in"])
            
            print(f"✅ Login successful as '{username}'")
            print(f"   Token expires at: {self.expires_at.strftime('%Y-%m-%d %H:%M:%S')}")
            
            return data
    
    async def refresh(self) -> dict:
        """
        Refresh access token menggunakan refresh token
        
        Returns:
            dict: Token response dari API
        """
        if not self.refresh_token:
            raise ValueError("No refresh token available. Please login first.")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/auth/refresh",
                json={"refresh_token": self.refresh_token}
            )
            response.raise_for_status()
            
            data = response.json()
            self.access_token = data["access_token"]
            self.refresh_token = data["refresh_token"]
            self.expires_at = datetime.now() + timedelta(seconds=data["expires_in"])
            
            print(f"🔄 Token refreshed")
            print(f"   New token expires at: {self.expires_at.strftime('%Y-%m-%d %H:%M:%S')}")
            
            return data
    
    async def ensure_token_valid(self):
        """
        Pastikan access token masih valid, refresh jika akan expired dalam 1 menit
        """
        if not self.access_token:
            raise ValueError("Not logged in. Please call login() first.")
        
        if self.expires_at and datetime.now() >= (self.expires_at - timedelta(minutes=1)):
            await self.refresh()
    
    def get_headers(self) -> dict:
        """Get headers dengan Authorization Bearer token"""
        if not self.access_token:
            raise ValueError("Not logged in. Please call login() first.")
        return {"Authorization": f"Bearer {self.access_token}"}
    
    async def get_me(self) -> dict:
        """
        Get informasi user yang sedang login
        
        Returns:
            dict: User info
        """
        await self.ensure_token_valid()
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/me",
                headers=self.get_headers()
            )
            response.raise_for_status()
            return response.json()
    
    async def chat(self, prompt: str) -> dict:
        """
        Chat dengan LLM
        
        Args:
            prompt: Pertanyaan atau pesan ke LLM
            
        Returns:
            dict: Response dari LLM
        """
        await self.ensure_token_valid()
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/llm/chat",
                headers=self.get_headers(),
                json={"prompt": prompt}
            )
            response.raise_for_status()
            return response.json()
    
    async def logout(self):
        """Logout dan revoke refresh token"""
        if not self.refresh_token:
            print("⚠️  Not logged in")
            return
        
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self.base_url}/auth/logout",
                json={"refresh_token": self.refresh_token}
            )
        
        self.access_token = None
        self.refresh_token = None
        self.expires_at = None
        
        print("👋 Logged out successfully")


async def main():
    """Example usage"""
    
    # Initialize client
    client = IPPLChatbotClient("http://localhost:8000")
    
    print("=" * 60)
    print("IPPL Chatbot Python Client Example")
    print("=" * 60)
    print()
    
    try:
        # 1. Login
        print("1️⃣  Login...")
        await client.login(username="dev", password="dev")
        print()
        
        # 2. Get user info
        print("2️⃣  Get user info...")
        user_info = await client.get_me()
        print(f"   Username: {user_info['username']}")
        print(f"   Email: {user_info['email']}")
        print(f"   Full name: {user_info['full_name']}")
        print(f"   Roles: {', '.join(user_info['roles'][:3])}...")
        print()
        
        # 3. Chat with LLM
        print("3️⃣  Chat with LLM...")
        questions = [
            "Siapa kamu?",
            "Apa itu Python?",
            "Jelaskan JWT dalam 1 kalimat"
        ]
        
        for i, question in enumerate(questions, 1):
            print(f"\n   Q{i}: {question}")
            try:
                response = await client.chat(question)
                answer = response['answer']
                # Truncate long answers
                if len(answer) > 150:
                    answer = answer[:150] + "..."
                print(f"   A{i}: {answer}")
            except Exception as e:
                print(f"   ⚠️  Error: {e}")
        
        print()
        
        # 4. Test token refresh
        print("4️⃣  Test token refresh...")
        await client.refresh()
        print()
        
        # 5. Verify new token works
        print("5️⃣  Verify new token...")
        user_info = await client.get_me()
        print(f"   ✅ New token works! Still logged in as {user_info['username']}")
        print()
        
        # 6. Logout
        print("6️⃣  Logout...")
        await client.logout()
        
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP Error: {e.response.status_code}")
        print(f"   {e.response.json()}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print()
    print("=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
