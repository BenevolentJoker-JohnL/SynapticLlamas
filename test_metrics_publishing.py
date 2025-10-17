#!/usr/bin/env python3
"""
Test script to verify metrics publishing to Redis for dashboard display.

This simulates a SynapticLlamas request and verifies that:
1. Metrics are calculated (P50/P95/P99)
2. Metrics are published to Redis
3. Dashboard can retrieve the metrics
"""
import json
import time
import redis
from node_registry import NodeRegistry
from sollol_load_balancer import SOLLOLLoadBalancer

print("=" * 80)
print("TESTING SYNAPTICLLAMAS METRICS PUBLISHING TO REDIS")
print("=" * 80)

# Step 1: Create registry and add test nodes
print("\n1. Creating NodeRegistry and adding test nodes...")
registry = NodeRegistry()

# Add some test nodes (from config)
test_nodes = [
    "http://10.9.66.154:11434",
    "http://10.9.66.48:11434",
    "http://10.9.66.90:11434"
]

for node_url in test_nodes:
    try:
        node = registry.add_node(node_url)
        print(f"   ✓ Added node: {node_url}")
    except Exception as e:
        print(f"   ✗ Failed to add {node_url}: {e}")

healthy = registry.get_healthy_nodes()
print(f"\n   Healthy nodes: {len(healthy)}")

if len(healthy) == 0:
    print("\n⚠️  No healthy nodes available. Test requires at least one healthy node.")
    exit(1)

# Step 2: Create load balancer (with Redis publishing enabled)
print("\n2. Creating SOLLOLLoadBalancer with Redis publishing...")
lb = SOLLOLLoadBalancer(registry, enable_gpu_control=False)
print("   ✓ Load balancer created")

# Wait a moment for Redis connection
time.sleep(1)

# Step 3: Simulate some requests to generate metrics
print("\n3. Simulating requests to generate metrics...")

# Create a test payload
test_payload = {
    "model": "llama3.2",
    "prompt": "Test request for metrics",
    "stream": False
}

num_requests = 5
for i in range(num_requests):
    print(f"   Simulating request {i+1}/{num_requests}...")

    # Route the request
    decision = lb.route_request(test_payload, agent_name="TestAgent", priority=5)
    print(f"      → Routed to: {decision.node.url}")

    # Simulate request execution with varying durations
    simulated_duration_ms = 1000 + (i * 500)  # 1000ms, 1500ms, 2000ms, 2500ms, 3000ms

    # Record the performance
    lb.record_performance(
        decision=decision,
        actual_duration_ms=simulated_duration_ms,
        success=True
    )
    print(f"      → Recorded: {simulated_duration_ms}ms (success)")

# Step 4: Check metrics in MetricsCollector
print("\n4. Checking metrics in MetricsCollector...")
summary = lb.metrics.get_summary()

print(f"   Total requests: {summary['total_requests']}")
print(f"   Successful requests: {summary['successful_requests']}")
print(f"   Success rate: {summary['success_rate']:.2%}")
print(f"   Average duration: {summary['avg_duration_ms']:.0f}ms")
print(f"   P50 latency: {summary['p50_latency_ms']:.0f}ms")
print(f"   P95 latency: {summary['p95_latency_ms']:.0f}ms")
print(f"   P99 latency: {summary['p99_latency_ms']:.0f}ms")

# Step 5: Wait for background thread to publish to Redis
print("\n5. Waiting for metrics to be published to Redis...")
print("   (Background thread publishes every 5 seconds)")
time.sleep(6)  # Wait a bit more than 5 seconds

# Step 6: Check Redis for published metrics
print("\n6. Checking Redis for published metrics...")
try:
    redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
    redis_client.ping()
    print("   ✓ Connected to Redis")

    # Get the metrics key
    metrics_json = redis_client.get("sollol:router:metadata")

    if metrics_json:
        metrics = json.loads(metrics_json)
        print("   ✓ Metrics found in Redis!")
        print(f"\n   Source: {metrics.get('source', 'unknown')}")

        analytics = metrics.get('metrics', {}).get('analytics', {})
        if analytics:
            print("\n   Analytics Metrics:")
            print(f"      P50 latency: {analytics.get('p50_latency_ms', 0):.0f}ms")
            print(f"      P95 latency: {analytics.get('p95_latency_ms', 0):.0f}ms")
            print(f"      P99 latency: {analytics.get('p99_latency_ms', 0):.0f}ms")
            print(f"      Success rate: {analytics.get('success_rate', 0):.2%}")
            print(f"      Total requests: {analytics.get('total_requests', 0)}")

        synaptic = metrics.get('metrics', {}).get('synaptic_llamas', {})
        if synaptic:
            print("\n   SynapticLlamas Metrics:")
            print(f"      Total nodes: {synaptic.get('total_nodes', 0)}")
            print(f"      Healthy nodes: {synaptic.get('healthy_nodes', 0)}")
            print(f"      GPU nodes: {synaptic.get('gpu_nodes', 0)}")
            print(f"      Routing decisions: {synaptic.get('routing_decisions', 0)}")

        # Verify P50/P95/P99 are non-zero
        if analytics.get('p50_latency_ms', 0) > 0:
            print("\n   ✅ SUCCESS! P50/P95/P99 metrics are non-zero and available for dashboard!")
        else:
            print("\n   ⚠️  WARNING: P50/P95/P99 metrics are still zero")
    else:
        print("   ✗ No metrics found in Redis at key 'sollol:router:metadata'")
        print("   This might mean the background thread hasn't published yet.")
        print("   Try waiting longer or check logs.")

except Exception as e:
    print(f"   ✗ Error checking Redis: {e}")

# Step 7: Cleanup
print("\n7. Cleaning up...")
lb.shutdown()
print("   ✓ Load balancer shutdown")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
print("\nIf P50/P95/P99 metrics are non-zero, the dashboard should now display them!")
print("You can verify by:")
print("  1. Opening the dashboard at http://localhost:8080")
print("  2. Checking the P50/P95/P99 latency metrics section")
print("  3. Running: redis-cli GET sollol:router:metadata | python -m json.tool")
