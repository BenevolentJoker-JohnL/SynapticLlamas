# SynapticLlamas - Quick Start Guide

## 🚀 Quick Start (Docker - Recommended)

### Option 1: Docker Compose (Easiest)

```bash
# Clone the repository
git clone https://github.com/BenevolentJoker-JohnL/SynapticLlamas.git
cd SynapticLlamas

# Start everything (SynapticLlamas + Ollama)
docker-compose up -d

# Run the interactive CLI
docker-compose exec synapticllamas python main.py --interactive
```

### Option 2: Docker with existing Ollama

```bash
# Build the image
docker build -t synapticllamas .

# Run (assumes Ollama is on host at localhost:11434)
docker run -it --network host synapticllamas --interactive
```

## 🛠️ Manual Installation

### Prerequisites

- Python 3.10+
- Ollama installed and running ([ollama.ai](https://ollama.ai))
- At least one model pulled (e.g., `ollama pull llama3.2`)

### Installation

```bash
# Clone repository
git clone https://github.com/BenevolentJoker-JohnL/SynapticLlamas.git
cd SynapticLlamas

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run interactive mode
python main.py --interactive
```

## 📖 Basic Usage

### Interactive Mode (Recommended for first use)

```bash
python main.py --interactive
```

Inside the CLI:

```
# Enable collaborative mode for best results
SynapticLlamas> collab on

# Enable AST quality voting (optional but recommended)
SynapticLlamas> ast on
SynapticLlamas> quality 0.7

# Ask a question
SynapticLlamas> Explain quantum entanglement
```

### Single Query Mode

```bash
python main.py -i "Explain quantum computing" --model llama3.2 --metrics
```

### Distributed Mode with Multiple Nodes

```bash
# Start in distributed mode
python main.py --interactive --distributed

# Inside CLI, add nodes
SynapticLlamas> add http://192.168.1.100:11434
SynapticLlamas> add http://192.168.1.101:11434

# Auto-discover nodes on your network
SynapticLlamas> discover

# Check node status
SynapticLlamas> nodes
SynapticLlamas> health
```

## 🎯 Key Commands

| Command | Description |
|---------|-------------|
| `collab on/off` | Toggle collaborative workflow |
| `ast on/off` | Toggle quality voting |
| `quality <0.0-1.0>` | Set quality threshold |
| `refine <n>` | Set refinement rounds |
| `timeout <sec>` | Set inference timeout |
| `nodes` | List all Ollama nodes |
| `add <url>` | Add Ollama node |
| `discover` | Auto-discover nodes |
| `health` | Health check all nodes |
| `status` | Show current config |
| `metrics` | Show last query metrics |
| `benchmark` | Run auto-benchmark |

## 🔧 Configuration

### Set Quality Standards

```bash
# High quality (slower, more thorough)
SynapticLlamas> quality 0.9
SynapticLlamas> refine 2
SynapticLlamas> qretries 3

# Balanced (default)
SynapticLlamas> quality 0.7
SynapticLlamas> refine 1
SynapticLlamas> qretries 2

# Fast (lower quality, faster results)
SynapticLlamas> quality 0.5
SynapticLlamas> refine 0
SynapticLlamas> ast off
```

### Network Discovery

```bash
# Auto-detect local network
SynapticLlamas> discover

# Scan specific network
SynapticLlamas> discover 192.168.1.0/24

# Save node configuration
SynapticLlamas> save nodes.json

# Load node configuration
SynapticLlamas> load nodes.json
```

## 📊 Example Workflow

```bash
# 1. Start with collaborative mode
SynapticLlamas> collab on
SynapticLlamas> ast on
SynapticLlamas> quality 0.8

# 2. Ask complex question
SynapticLlamas> Explain the differences between supervised and unsupervised learning

# 3. View results with phase timings and quality scores
# Output shows:
# - Phase timings for each step
# - Quality voting scores
# - Node attribution
# - Beautiful markdown answer

# 4. Check metrics
SynapticLlamas> metrics
```

## 🐛 Troubleshooting

### Connection Issues

```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Test node connectivity
SynapticLlamas> health

# Add node manually if discovery fails
SynapticLlamas> add http://localhost:11434
```

### Timeout Issues

```bash
# Increase timeout for slow hardware
SynapticLlamas> timeout 600  # 10 minutes

# Lower quality threshold for CPU-only systems
SynapticLlamas> quality 0.6
```

### Quality Voting Failures

```bash
# Reduce quality requirements
SynapticLlamas> quality 0.6
SynapticLlamas> qretries 1

# Or disable AST voting
SynapticLlamas> ast off
```

## 🎓 Next Steps

1. **Explore distributed mode** - Add multiple Ollama nodes for parallel processing
2. **Experiment with quality settings** - Find the right balance for your use case
3. **Try different models** - Switch between llama3.2, mistral, etc.
4. **Run benchmarks** - Compare strategies and optimize performance
5. **Check the full README** - Learn about advanced features

## 📚 Documentation

- [README.md](README.md) - Full documentation
- [Architecture Overview](README.md#architecture) - System design
- [Advanced Features](README.md#advanced-features) - Deep dive

## 🆘 Getting Help

- GitHub Issues: https://github.com/BenevolentJoker-JohnL/SynapticLlamas/issues
- Check logs for detailed error messages
- Use `help` command in interactive mode

---

**Happy Orchestrating!** 🧠🦙
