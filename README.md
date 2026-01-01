# NoHaram DNS 🛡️

> **An AI-Powered, Self-Learning Ethical Internet Filter.**
> *Protecting users from pornography, gambling, and toxicity without compromising speed.*

**Live Deployment:** [dns.noharam.app](https://dns.noharam.app)

## 📖 Overview

NoHaram DNS is a hybrid content filtering system that solves the "velocity problem" of the modern internet. Unlike traditional filters that rely solely on static blocklists, this system uses a **Fine-Tuned NLP Model** to analyze unknown domains in real-time.

It employs a **"Fail-Open" Asynchronous Architecture**: users are never blocked from waiting for an AI scan. Instead, unknown traffic is allowed instantly, scanned in the background, and blocked globally within seconds if deemed unsafe.

## 🛠️ System Architecture

The system follows a Lambda Architecture, splitting the workload between a high-speed "Hot Path" (CoreDNS) and an intelligent "Cold Path" (AI Worker).

1. **The Bridge:** Tails DNS logs in real-time and pushes unknown domains to a **Redis Queue**.
2. **The Worker:** A Python process that pulls domains, scrapes metadata (Meta tags/Titles), and runs the NLP Classifier.
3. **The Manager:** Updates the `final_blocklist.txt` and reloads CoreDNS if a threat is found.

## 🧠 AI Performance & Research

The core intelligence is derived from a DistilBERT model trained on a custom dataset of 120,000+ samples, including the *Big Porn Dataset*, *WikiText*, and *AG News*.

### Stress Test Results (Phase 2)

We evaluated the model against completely unseen "Zero-Day" datasets to ensure robustness against slang and technical jargon.

| Class | Dataset Source | Precision | Recall | F1-Score |
| --- | --- | --- | --- | --- |
| **SAFE** | DBPedia / News | 0.96 | 0.96 | **0.98** |
| **UNSAFE** | Toxic Tweets | 0.92 | **1.00** | **0.94** |
| **MEDICAL** | Medical Exams | 0.95 | 0.90 | **0.95** |

### Visualizations

The model demonstrates **zero leakage** for unsafe content (1.00 Recall) and successfully distinguishes medical terms from explicit content.

| Confusion Matrix | ROC Curve |
| --- | --- |
|  |  |

> *Note: See `research/notebooks/Nlp_model_v2.ipynb` for full training code.*

## 🚀 Installation & Usage

### Prerequisites

* Python 3.9+
* Redis
* CoreDNS
* Example `.env` configuration

### 1. Clone the Repository

```bash
git clone https://github.com/hamzamalik22/block_haram.git
cd block_haram

```

### 2. Install Dependencies

```bash
pip install -r requirements.txt

```

### 3. Configuration

Set up your environment variables and DNS config.

```bash
cp .env.example .env
cp Corefile.example Corefile
# Edit .env if you need to change Redis ports or API keys
nano .env

```

### 4. Start Support Services

Ensure the database and DNS server are running.

```bash
# Start Redis (Message Broker)
redis-server &

# Start CoreDNS (The Gatekeeper)
coredns -conf Corefile &

```

### 5. Start the AI System

*Note: Run these in separate terminal windows or use `docker-compose`.*

**Terminal A: The Bridge (Log Monitor)**

```bash
python src/bridge/log_monitor.py

```

**Terminal B: The AI Worker (Classifier)**

```bash
python src/ai_worker/worker.py

```

**Terminal C: Admin Dashboard**

```bash
python src/dashboard/app.py

```

*Access the dashboard at `http://localhost:5000` to view live logs and manage whitelists.*

## 📂 Project Structure

```text
NoHaram-DNS/
├── research/                  # The "Lab"
│   ├── notebooks/             # Jupyter Notebooks & Training Logs
│   └── metrics/               # Performance graphs (Confusion Matrix, ROC)
├── src/                       # The "Factory"
│   ├── ai_worker/             # DistilBERT Inference & Scraping Logic
│   ├── bridge/                # DNS Log to Redis Bridge
│   ├── dashboard/             # Flask Admin Interface
│   └── dns_core/              # CoreDNS Configurations
├── data/
│   └── blocklists/            # Active block/allow lists
└── requirements.txt           # Python Dependencies

```


## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.