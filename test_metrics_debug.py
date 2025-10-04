#!/usr/bin/env python3
"""
Test script to debug metrics tracking.
This will show all the debug logging to trace where metrics are going.
"""
import logging
import sys

# Set up logging to show INFO level
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

from node_registry import NodeRegistry
from sollol_load_balancer import SOLLOLLoadBalancer
from agents.researcher import Researcher

print("=" * 80)
print("METRICS DEBUG TEST")
print("=" * 80)

# Create registry and add your two nodes
registry = NodeRegistry()
print("\n1. Adding nodes to registry...")
node1 = registry.add_node("http://10.9.66.154:11434", name="node-154")
node2 = registry.add_node("http://10.9.66.157:11434", name="node-157")

print(f"\nRegistry has {len(registry)} nodes:")
for url in registry.nodes.keys():
    print(f"  - {url}")

# Create load balancer
print("\n2. Creating SOLLOL load balancer...")
lb = SOLLOLLoadBalancer(registry)

# Create a test agent
print("\n3. Creating test agent...")
agent = Researcher(model="llama3.2")
agent._load_balancer = lb

print("\n4. Running a simple test query...")
print("=" * 80)

result = agent.process("What is 2+2?")

print("\n" + "=" * 80)
print("5. Checking final metrics...")
print("=" * 80)

for url, node in registry.nodes.items():
    print(f"\nNode: {url}")
    print(f"  Object ID: {id(node)}")
    print(f"  Total requests: {node.metrics.total_requests}")
    print(f"  Avg response time: {node.metrics.avg_response_time:.2f}s")
    print(f"  Avg latency: {node.metrics.avg_latency:.0f}ms")
    print(f"  Load score: {node.calculate_load_score():.1f}")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
