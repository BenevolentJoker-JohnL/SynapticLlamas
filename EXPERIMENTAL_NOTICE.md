# Experimental Features Notice

## Model Sharding (llama.cpp RPC Integration)

### Status: EXPERIMENTAL

Model sharding via llama.cpp RPC is currently an **experimental feature** in SynapticLlamas.

### What This Means

**Current State:**
- ✅ **Functional for testing**: Works with 13B models across 2-3 nodes (verified)
- ⚠️ **Not production-ready**: Requires extensive testing and optimization
- ⚠️ **Performance limitations**: Network overhead, slower than local inference
- ⚠️ **Limited validation**: Larger models (70B+) need more testing

**Use Cases:**
- ✅ Research and development
- ✅ Testing and validation
- ✅ Proof-of-concept demonstrations
- ✅ Learning distributed inference concepts
- ❌ Production workloads (not recommended without extensive testing)

### Known Limitations

1. **Startup Time**: 2-5 minutes for 13B models, potentially longer for 70B+
2. **Inference Speed**: Slower than local due to network communication (~5 tok/s vs ~20 tok/s)
3. **Network Requirements**: Requires stable, low-latency network between nodes
4. **Configuration**: Manual RPC server setup required on each node
5. **Testing Coverage**: Limited real-world usage and edge case testing

### Future Development Needed

To move this feature from experimental to production-ready:

- [ ] Performance optimization (reduce network overhead)
- [ ] Extensive testing with 70B+ models
- [ ] Automated RPC server deployment
- [ ] Better error handling and recovery
- [ ] Comprehensive benchmarking across different network conditions
- [ ] Load balancing improvements for heterogeneous clusters
- [ ] Documentation of failure modes and recovery procedures

### When to Use Model Sharding

**Good Use Cases:**
- Model doesn't fit on single machine
- Experimenting with distributed inference
- Research projects
- Development and testing
- Learning distributed systems

**Better Alternatives:**
- If model fits on single machine → use local Ollama (much faster)
- If need production reliability → use cloud services or larger hardware
- If need guaranteed performance → use local inference

### Recommended Approach

1. **Start local**: Try with single Ollama instance first
2. **Test small**: Verify with 13B models before attempting 70B+
3. **Measure carefully**: Benchmark performance for your specific use case
4. **Have fallback**: Keep local inference option available
5. **Report issues**: Help improve the feature by reporting bugs and performance data

### Documentation

For setup and usage instructions, see:
- [DISTRIBUTED_INFERENCE.md](DISTRIBUTED_INFERENCE.md) - Main setup guide
- [MODEL_SHARDING_COMPLETE.md](MODEL_SHARDING_COMPLETE.md) - Proof of concept
- [LLAMA_CPP_INTEGRATION.md](LLAMA_CPP_INTEGRATION.md) - Technical integration details

### Feedback Welcome

If you test this feature:
- Report performance metrics (latency, throughput, startup time)
- Document any issues or unexpected behavior
- Share your use case and requirements
- Contribute improvements via pull requests

---

**Remember**: Experimental features are valuable for research and development, but require caution for production use. Always test thoroughly in your specific environment before relying on experimental features.
