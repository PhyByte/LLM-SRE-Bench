# LLM Observability Benchmark Suite

## Project Overview
Build a benchmarking framework to evaluate and compare LLMs (Grok, Claude, GPT, Llama, etc.) on their ability to analyze logs, metrics, detect anomalies, and identify patterns in DevOps / SRE scenarios.

The tool should run standardized tests, compute detailed scores, and produce comparison reports.

## Requirements

### 1. Configuration (`models.json`)
Create a flexible config file:

```json
{
  "runs_per_test": 3,
  "temperature": 0.0,
  "max_tokens": 4096,
  "models": [
    {
      "name": "grok-4",
      "provider": "xai",
      "base_url": "https://api.x.ai/v1",
      "api_key": "xai-...",
      "model_id": "grok-4"
    },
    {
      "name": "claude-3-5-sonnet",
      "provider": "anthropic",
      "api_key": "...",
      "model_id": "claude-3-5-sonnet-20240620"
    },
    {
      "name": "llama3.1-70b",
      "provider": "ollama",
      "model_id": "llama3.1:70b"
    }
  ]
}

### 2. Test Categories & Scoring (Weighted)

| Category                        | Weight | Evaluation Metrics                          |
|---------------------------------|--------|---------------------------------------------|
| Log Parsing                     | 20%    | Template accuracy, F1                      |
| Anomaly Detection               | 30%    | Precision, Recall, F1                      |
| Pattern & Correlation Detection | 20%    | Pattern coverage + correlation accuracy    |
| Metrics Time-Series Analysis    | 15%    | Anomaly detection on numeric series        |
| Root Cause & Summarization      | 10%    | Quality (LLM-as-judge + ROUGE)             |
| Efficiency & Consistency        | 5%     | Avg latency, token cost, std dev across runs |

**Global Score** = Weighted average (0-100)

### 3. Datasets (Start with Public)
- Loghub datasets (HDFS, BGL, Thunderbird, etc.)
- LogEval benchmark tasks (parsing, anomaly detection, diagnosis)
- Synthetic metrics time-series (with injected anomalies)
- Include a small sample in the repo for quick testing

### 4. Technical Requirements
- Python 3.11+
- Support OpenAI-compatible clients + Anthropic + Ollama
- Use Pydantic for strict JSON output validation
- Libraries: `pandas`, `scikit-learn`, `rich`, `httpx`, `python-dotenv`, `typer`
- Modular design: `tests/`, `scorers/`, `datasets/`, `reports/`
- CLI interface with `typer`
- Caching of LLM responses (optional but recommended)
- Error handling and rate-limit resilience

### 5. Output
The script should generate in a `results/` folder:
- `comparison_table.md` (beautiful ranked table)
- `detailed_results.csv`
- `summary_report.md` (with key insights and recommendations)
- Console progress with rich tables

### 6. Nice-to-Haves
- Progress bars and live status
- Option to test only specific categories (`--category anomaly`)
- Support for few-shot examples
- Export results to JSON for further analysis
- README with usage examples and how to add new models/datasets

## Task for the Builder
Please generate the **full project structure** with all necessary files:
- `main.py` or `benchmark.py` (entry point)
- Modular packages (`core/`, `evaluators/`, `utils/`, etc.)
- Example `models.json`
- Sample dataset loaders (include small dummy data)
- Prompt templates for each test category
- Scoring logic
- Full `README.md` with installation and usage instructions

Make the code clean, well-documented, modular, and production-ready. Use best practices for API clients and error handling.