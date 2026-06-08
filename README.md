# VIT Student MCP Server

A powerful local Model Context Protocol (MCP) server designed for VIT students. It seamlessly scrapes your VTOP profile using a headless Playwright browser and exposes all your academic data (Marks, Attendance, Exams, Assignments, Timetable) to Claude Desktop as an AI assistant tool.

**Key Features:**
- **Auto-Captcha Solving**: Uses a lightweight Neural Network (`ddddocr`) to automatically solve VTOP captchas.
- **Full Automation**: Injects JS exactly like the official Android App to safely extract data from VTOP.
- **SQLite Caching**: Saves everything locally so the MCP server responds instantly to Claude without needing to hit VTOP repeatedly.
- **Claude Integration**: Ask Claude questions like "What's my schedule tomorrow?", "Did I pass Cloud Computing?", or "Am I debarred in any subject?"

---

## 🛠️ Installation & Setup

### 1. Prerequisites
You need **Python 3.9+** and `pip` installed on your machine.
If you use Conda, it is highly recommended to create a new environment:
```bash
conda create -n vit-mcp python=3.11
conda activate vit-mcp
```

### 2. Install Dependencies
Clone this repository and install the required packages:
```bash
git clone https://github.com/Inesh03/VIT-STUDENT-MCP-SERVER.git
cd VIT-STUDENT-MCP-SERVER
pip install -r requirements.txt
```

### 3. Install Playwright Browsers
The scraper requires headless Chromium to run:
```bash
playwright install chromium
```

---

## 🔄 How to Sync Your Data
Before Claude can answer questions, you need to pull your latest data from VTOP into the local database.

Run the sync script in your terminal:
```bash
python src/sync.py
```
You will be prompted to enter your Registration Number and Password. The script will open a hidden browser, solve the Captcha automatically, and download your entire academic profile!

---

## 🤖 Connecting to Claude Desktop
To let Claude access your data, you need to add this project as an MCP Server.

1. Open your Claude Desktop Configuration File:
   - **Mac:** `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
2. Add the following entry, making sure to replace the path with the actual absolute path to the project on your machine:

```json
{
  "mcpServers": {
    "vit-student": {
      "command": "python",
      "args": [
        "/path/to/your/VIT-STUDENT-MCP-SERVER/src/server.py"
      ]
    }
  }
}
```
*(If you are using Conda, replace `"python"` with the absolute path to your Conda environment's python executable, e.g., `/opt/miniconda3/envs/vit-mcp/bin/python`)*

3. **Restart Claude Desktop**. You should now see the "plug" icon, meaning your VIT Assistant is ready!

---

## ⚠️ Disclaimer
This tool is entirely local. Your VTOP password is **never saved** anywhere, and your academic data is stored only in a local SQLite file (`vit_student.db`) on your own hard drive.
