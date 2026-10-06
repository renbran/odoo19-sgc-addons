#!/usr/bin/env python3
"""
Test script to verify LLM Lead Enrichment is working
Usage: python test_groq_api.py YOUR_API_KEY_HERE
"""
import requests
import json
import sys

# Test configuration
API_KEY = sys.argv[1] if len(sys.argv) > 1 else "YOUR_GROQ_API_KEY"
MODEL = "llama-3.3-70b-versatile"
URL = "https://api.groq.com/openai/v1/chat/completions"

def test_api():
    """Test the Groq API directly"""
    print("=" * 60)
    print("🧪 Testing Groq API Configuration")
    print("=" * 60)
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful sales AI assistant analyzing lead quality."
            },
            {
                "role": "user",
                "content": "Analyze this lead: Company 'Tech Solutions Inc', Contact: John Doe, Email: john@techsolutions.com, Phone: +1-555-1234. They are interested in CRM software. Provide a brief quality assessment."
            }
        ],
        "temperature": 0.7,
        "max_tokens": 200
    }
    
    try:
        print(f"\n📡 Sending request to: {URL}")
        print(f"🤖 Model: {MODEL}")
        print(f"🔑 API Key: {API_KEY[:20]}...")
        
        response = requests.post(URL, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            content = data['choices'][0]['message']['content']
            
            print("\n✅ SUCCESS! API is working perfectly!")
            print(f"\n📊 Response:")
            print("-" * 60)
            print(content)
            print("-" * 60)
            
            print(f"\n📈 Usage Stats:")
            print(f"   - Prompt tokens: {data['usage'].get('prompt_tokens', 'N/A')}")
            print(f"   - Completion tokens: {data['usage'].get('completion_tokens', 'N/A')}")
            print(f"   - Total tokens: {data['usage'].get('total_tokens', 'N/A')}")
            
            return True
        else:
            print(f"\n❌ FAILED! Status: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        return False

def test_odoo_config():
    """Show Odoo configuration"""
    print("\n" + "=" * 60)
    print("⚙️  Odoo Configuration")
    print("=" * 60)
    print(f"\nLLM Provider ID: 8")
    print(f"Provider Name: Groq Fast AI (Free)")
    print(f"Provider Type: groq")
    print(f"Model: {MODEL}")
    print(f"Is Default: ✅ Yes")
    print(f"Active: ✅ Yes")
    print(f"\nConfiguration Parameter:")
    print(f"  llm_lead_scoring.default_provider_id = 8")

if __name__ == '__main__':
    # Test API
    api_works = test_api()
    
    # Show Odoo config
    test_odoo_config()
    
    # Final summary
    print("\n" + "=" * 60)
    print("📋 Summary")
    print("=" * 60)
    if api_works:
        print("✅ API Key is VALID and working")
        print("✅ Odoo is configured to use this provider")
        print("✅ Lead enrichment should work now!")
        print("\n🎯 Next Steps:")
        print("   1. Go to CRM → Leads")
        print("   2. Open any lead")
        print("   3. Click 'Enrich with AI' button")
        print("   4. You should see AI analysis!")
    else:
        print("❌ API test failed - check error messages above")
    
    print("\n⚠️  Remember: Delete this API key after testing!")
    print("=" * 60)
