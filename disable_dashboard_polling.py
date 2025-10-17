#!/usr/bin/env python3
"""
Disable aggressive dashboard polling in SynapticLlamas

This script provides options to reduce or eliminate HTTP polling from the dashboard.
"""

import sys

print("""
🛑 DASHBOARD POLLING OPTIONS

Current dashboard design polls Ollama nodes every 30 seconds (previously 2s).
This is still not ideal for production systems.

BETTER APPROACHES:

1. ✅ USE REDIS PUB/SUB (Recommended)
   - Enable Redis logging: `redis on` in SynapticLlamas
   - Subscribe to events instead of polling
   - Zero HTTP overhead
   - Real-time updates

   Commands:
   SynapticLlamas> redis on

   Then in another terminal:
   redis-cli subscribe synapticllamas:llama_cpp:logs

2. ✅ DISABLE DASHBOARD MONITORING
   - Simply don't run the `dashboard` command
   - Use CLI commands instead: `status`, `nodes`, `health`

3. ✅ USE ON-DEMAND QUERIES
   - Run queries only when you need info:
     SynapticLlamas> nodes      # Show node status
     SynapticLlamas> status     # Show system status
     SynapticLlamas> health     # Run health check

4. ⚠️  INCREASE POLLING INTERVAL (Already done - 30s)
   - Less aggressive than before
   - Still not ideal for production
   - File: dashboard_server.py lines 402, 630, 244

5. 🔧 MAKE POLLING CONFIGURABLE
   - Add environment variable: DASHBOARD_POLL_INTERVAL
   - Default: 30 seconds
   - Set to 0 to disable polling entirely

RECOMMENDATION:
For production systems, use Redis pub/sub (option 1) instead of HTTP polling.
This is the correct architecture for real-time monitoring.

For development/testing:
- Current 30-second polling is acceptable
- Or disable dashboard and use CLI commands
""")

# Check if user wants to apply additional changes
response = input("\nWould you like to disable Ollama polling entirely? (y/N): ").strip().lower()

if response == 'y':
    import os

    dashboard_path = os.path.join(os.path.dirname(__file__), 'dashboard_server.py')

    if not os.path.exists(dashboard_path):
        print("❌ dashboard_server.py not found")
        sys.exit(1)

    print("\n⚠️  To disable Ollama polling entirely, you would need to:")
    print("   1. Comment out ws_ollama_logs() WebSocket endpoint")
    print("   2. Remove Ollama tab from dashboard.html")
    print("   3. Use Redis pub/sub for real-time monitoring instead")
    print("\n💡 Instead, I recommend just using Redis logging:")
    print("   SynapticLlamas> redis on")
    print("\n   This gives you real-time monitoring WITHOUT HTTP polling!")
else:
    print("\n✅ No changes made. Current 30-second polling will remain.")
    print("💡 Tip: Use 'redis on' for real-time monitoring without HTTP spam")
